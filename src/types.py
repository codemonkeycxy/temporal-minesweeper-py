"""Type definitions for Temporal Minesweeper."""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from enum import Enum


@dataclass
class Cell:
    """Represents a single cell on the minesweeper board."""
    is_mine: bool
    is_revealed: bool
    is_flagged: bool
    neighbor_mines: int
    row: int
    col: int


@dataclass
class GameBoard:
    """Represents the game board."""
    cells: List[List[Cell]]
    width: int
    height: int
    mine_count: int


class GameStatus(str, Enum):
    """Possible game states."""
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    WON = 'WON'
    LOST = 'LOST'
    CLOSED = 'CLOSED'


@dataclass
class GameState:
    """Current state of the game."""
    id: str
    board: GameBoard
    status: GameStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    flags_used: int = 0
    cells_revealed: int = 0


@dataclass
class MoveRequest:
    """Request to make a move."""
    row: int
    col: int
    action: str  # 'reveal', 'flag', 'unflag', 'chord'


@dataclass
class GameConfig:
    """Configuration for creating a new game."""
    width: int
    height: int
    mine_count: int


@dataclass
class CreateGameRequest:
    """Request to create a new game."""
    config: GameConfig


@dataclass
class GameResponse:
    """Response containing game state."""
    game_state: GameState
    message: Optional[str] = None