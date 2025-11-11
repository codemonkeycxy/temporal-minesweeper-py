"""Temporal activities for game logic."""
import random
import copy
from temporalio import activity
from typing import List
from src.types import Cell, GameBoard, GameConfig, GameState, GameStatus


def count_neighbor_mines(cells: List[List[Cell]], row: int, col: int, width: int, height: int) -> int:
    """Count the number of mines in neighboring cells."""
    count = 0
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            new_row = row + dr
            new_col = col + dc
            if 0 <= new_row < height and 0 <= new_col < width:
                if cells[new_row][new_col].is_mine:
                    count += 1
    return count


@activity.defn
async def create_game_board(config: GameConfig) -> GameBoard:
    """Create a new game board with randomly placed mines."""
    width, height, mine_count = config.width, config.height, config.mine_count

    # Initialize empty board
    cells: List[List[Cell]] = []
    for row in range(height):
        cells.append([])
        for col in range(width):
            cells[row].append(Cell(
                is_mine=False,
                is_revealed=False,
                is_flagged=False,
                neighbor_mines=0,
                row=row,
                col=col
            ))

    # Place mines randomly using Fisher-Yates shuffle
    positions = [(row, col) for row in range(height) for col in range(width)]
    random.shuffle(positions)

    # Place mines
    for i in range(min(mine_count, len(positions))):
        row, col = positions[i]
        cells[row][col].is_mine = True

    # Calculate neighbor mine counts
    for row in range(height):
        for col in range(width):
            if not cells[row][col].is_mine:
                cells[row][col].neighbor_mines = count_neighbor_mines(cells, row, col, width, height)

    return GameBoard(
        cells=cells,
        width=width,
        height=height,
        mine_count=mine_count
    )


def reveal_cell_recursive(cells: List[List[Cell]], row: int, col: int, width: int, height: int) -> None:
    """Recursively reveal cells (cascade logic)."""
    if row < 0 or row >= height or col < 0 or col >= width:
        return

    cell = cells[row][col]
    if cell.is_revealed or cell.is_flagged or cell.is_mine:
        return

    cell.is_revealed = True

    # If this cell has no neighboring mines, reveal all neighbors
    if cell.neighbor_mines == 0:
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                reveal_cell_recursive(cells, row + dr, col + dc, width, height)


@activity.defn
async def reveal_cell(game_state: GameState, row: int, col: int) -> GameState:
    """Reveal a cell and potentially cascade to neighbors."""
    cell = game_state.board.cells[row][col]

    if cell.is_revealed or cell.is_flagged:
        return game_state

    # Deep clone the game state
    new_game_state = copy.deepcopy(game_state)

    if cell.is_mine:
        # Game over
        new_game_state.status = GameStatus.LOST
        new_game_state.end_time = activity.now()
        # Reveal all mines
        for r in range(new_game_state.board.height):
            for c in range(new_game_state.board.width):
                if new_game_state.board.cells[r][c].is_mine:
                    new_game_state.board.cells[r][c].is_revealed = True
    else:
        # Reveal the cell and potentially cascade
        reveal_cell_recursive(new_game_state.board.cells, row, col,
                            new_game_state.board.width, new_game_state.board.height)

        # Count revealed cells
        revealed_count = 0
        for r in range(new_game_state.board.height):
            for c in range(new_game_state.board.width):
                if new_game_state.board.cells[r][c].is_revealed:
                    revealed_count += 1

        new_game_state.cells_revealed = revealed_count

        # Check win condition
        total_cells = new_game_state.board.width * new_game_state.board.height
        if revealed_count == total_cells - new_game_state.board.mine_count:
            new_game_state.status = GameStatus.WON
            new_game_state.end_time = activity.now()

    return new_game_state


@activity.defn
async def toggle_flag(game_state: GameState, row: int, col: int) -> GameState:
    """Toggle flag on a cell."""
    cell = game_state.board.cells[row][col]

    if cell.is_revealed:
        return game_state

    # Deep clone the game state
    new_game_state = copy.deepcopy(game_state)
    new_cell = new_game_state.board.cells[row][col]

    new_cell.is_flagged = not new_cell.is_flagged

    # Update flag count
    flag_count = 0
    for r in range(new_game_state.board.height):
        for c in range(new_game_state.board.width):
            if new_game_state.board.cells[r][c].is_flagged:
                flag_count += 1

    new_game_state.flags_used = flag_count

    return new_game_state


@activity.defn
async def chord_reveal(game_state: GameState, row: int, col: int) -> GameState:
    """Mass open adjacent cells when flags match the cell's number."""
    cell = game_state.board.cells[row][col]

    # Can only chord on revealed cells with numbers
    if not cell.is_revealed or cell.is_mine or cell.neighbor_mines == 0:
        return game_state

    # Deep clone the game state
    new_game_state = copy.deepcopy(game_state)

    # Count flagged neighbors and collect unflagged, unrevealed neighbors
    flagged_count = 0
    neighbors_to_reveal = []

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue

            new_row = row + dr
            new_col = col + dc

            if 0 <= new_row < game_state.board.height and 0 <= new_col < game_state.board.width:
                neighbor = game_state.board.cells[new_row][new_col]

                if neighbor.is_flagged:
                    flagged_count += 1
                elif not neighbor.is_revealed:
                    neighbors_to_reveal.append((new_row, new_col))

    # Only proceed if flagged count matches the cell's number
    if flagged_count != cell.neighbor_mines:
        return game_state

    # Reveal all unflagged neighbors
    hit_mine = False
    for neighbor_row, neighbor_col in neighbors_to_reveal:
        neighbor_cell = new_game_state.board.cells[neighbor_row][neighbor_col]

        if neighbor_cell.is_mine:
            hit_mine = True
            neighbor_cell.is_revealed = True
        else:
            # Use recursive reveal for empty cells
            reveal_cell_recursive(new_game_state.board.cells, neighbor_row, neighbor_col,
                                new_game_state.board.width, new_game_state.board.height)

    if hit_mine:
        # Game over - reveal all mines
        new_game_state.status = GameStatus.LOST
        new_game_state.end_time = activity.now()
        for r in range(new_game_state.board.height):
            for c in range(new_game_state.board.width):
                if new_game_state.board.cells[r][c].is_mine:
                    new_game_state.board.cells[r][c].is_revealed = True
    else:
        # Count revealed cells and check win condition
        revealed_count = 0
        for r in range(new_game_state.board.height):
            for c in range(new_game_state.board.width):
                if new_game_state.board.cells[r][c].is_revealed:
                    revealed_count += 1

        new_game_state.cells_revealed = revealed_count

        total_cells = new_game_state.board.width * new_game_state.board.height
        if revealed_count == total_cells - new_game_state.board.mine_count:
            new_game_state.status = GameStatus.WON
            new_game_state.end_time = activity.now()

    return new_game_state
