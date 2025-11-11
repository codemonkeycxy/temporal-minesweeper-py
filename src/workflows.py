"""Temporal workflows for Minesweeper game."""
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.types import GameState, GameStatus, MoveRequest, GameConfig
    from src.activities import create_game_board, reveal_cell, toggle_flag, chord_reveal


@workflow.defn
class MinesweeperWorkflow:
    """Workflow that manages a single Minesweeper game."""

    def __init__(self):
        self.game_id: str = ""
        self.game_state: GameState | None = None
        self.last_activity_time: float = 0
        self.should_close: bool = False

    @workflow.run
    async def run(self, game_id: str, initial_config: GameConfig) -> None:
        """Main workflow entry point."""
        # Store game_id immediately so queries can access it during initialization
        self.game_id = game_id

        # Set initial activity time
        self.last_activity_time = workflow.time()

        # Create initial board
        initial_board = await workflow.execute_activity(
            create_game_board,
            initial_config,
            start_to_close_timeout=timedelta(seconds=60),
        )

        self.game_state = GameState(
            id=game_id,
            board=initial_board,
            status=GameStatus.NOT_STARTED,
            flags_used=0,
            cells_revealed=0
        )

        # Auto-close workflow after 24 hours of inactivity
        inactivity_timeout = timedelta(hours=24)
        check_interval = timedelta(minutes=1)

        try:
            while not self.should_close:
                # Wait for either close signal or timeout
                await workflow.wait_condition(
                    lambda: self.should_close or
                           (workflow.time() - self.last_activity_time) >= inactivity_timeout.total_seconds(),
                    timeout=check_interval.total_seconds()
                )

                if self.should_close:
                    break

                # Check if we've reached the inactivity timeout
                if (workflow.time() - self.last_activity_time) >= inactivity_timeout.total_seconds():
                    workflow.logger.info(f"Game {game_id} auto-closing due to 24 hours of inactivity")
                    break

        except Exception as error:
            workflow.logger.error(f"Error in workflow loop: {error}")

        # Mark the game as closed
        if self.game_state:
            self.game_state.status = GameStatus.CLOSED
            self.game_state.end_time = workflow.now()

        workflow.logger.info(f"Minesweeper workflow {game_id} completed")

    @workflow.signal
    async def make_move_signal(self, move_request: MoveRequest) -> None:
        """Signal to make a move (fire-and-forget)."""
        if not self.game_state or self.game_state.status in [GameStatus.WON, GameStatus.LOST, GameStatus.CLOSED]:
            return  # Game not ready or game is over, ignore moves

        # Update activity time
        self.last_activity_time = workflow.time()

        # Start the game on first move
        if self.game_state.status == GameStatus.NOT_STARTED:
            self.game_state.status = GameStatus.IN_PROGRESS
            self.game_state.start_time = workflow.now()

        row, col, action = move_request.row, move_request.col, move_request.action

        try:
            if action == 'reveal':
                self.game_state = await workflow.execute_activity(
                    reveal_cell,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
            elif action in ['flag', 'unflag']:
                self.game_state = await workflow.execute_activity(
                    toggle_flag,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
            elif action == 'chord':
                self.game_state = await workflow.execute_activity(
                    chord_reveal,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
        except Exception as error:
            workflow.logger.error(f"Error processing move: {error}")

    @workflow.update
    async def make_move_update(self, move_request: MoveRequest) -> GameState:
        """Update to make a move and return the updated state."""
        if not self.game_state:
            raise ValueError("Game state not initialized")

        if self.game_state.status in [GameStatus.WON, GameStatus.LOST, GameStatus.CLOSED]:
            return self.game_state  # Return current state if game is over

        # Update activity time
        self.last_activity_time = workflow.time()

        # Start the game on first move
        if self.game_state.status == GameStatus.NOT_STARTED:
            self.game_state.status = GameStatus.IN_PROGRESS
            self.game_state.start_time = workflow.now()

        row, col, action = move_request.row, move_request.col, move_request.action

        try:
            if action == 'reveal':
                self.game_state = await workflow.execute_activity(
                    reveal_cell,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
            elif action in ['flag', 'unflag']:
                self.game_state = await workflow.execute_activity(
                    toggle_flag,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
            elif action == 'chord':
                self.game_state = await workflow.execute_activity(
                    chord_reveal,
                    args=[self.game_state, row, col],
                    start_to_close_timeout=timedelta(seconds=60),
                )
        except Exception as error:
            workflow.logger.error(f"Error processing move: {error}")

        return self.game_state

    @workflow.signal
    async def restart_game_signal(self, config: GameConfig) -> None:
        """Signal to restart the game with new configuration."""
        if self.game_state and self.game_state.status == GameStatus.CLOSED:
            return  # Cannot restart closed games

        # Update activity time
        self.last_activity_time = workflow.time()

        new_board = await workflow.execute_activity(
            create_game_board,
            config,
            start_to_close_timeout=timedelta(seconds=60),
        )

        self.game_state = GameState(
            id=self.game_state.id if self.game_state else "",
            board=new_board,
            status=GameStatus.NOT_STARTED,
            flags_used=0,
            cells_revealed=0
        )

    @workflow.update
    async def restart_game_update(self, config: GameConfig) -> GameState:
        """Update to restart the game and return the new state."""
        if self.game_state and self.game_state.status == GameStatus.CLOSED:
            return self.game_state  # Cannot restart closed games

        # Update activity time
        self.last_activity_time = workflow.time()

        new_board = await workflow.execute_activity(
            create_game_board,
            config,
            start_to_close_timeout=timedelta(seconds=60),
        )

        game_id = self.game_state.id if self.game_state else ""
        self.game_state = GameState(
            id=game_id,
            board=new_board,
            status=GameStatus.NOT_STARTED,
            flags_used=0,
            cells_revealed=0
        )

        return self.game_state

    @workflow.signal
    def close_game_signal(self) -> None:
        """Signal to close the game."""
        self.should_close = True

    @workflow.query
    def get_game_state_query(self) -> GameState:
        """Query to get the current game state."""
        if not self.game_state:
            # Return a minimal valid state while initializing
            return GameState(
                id=self.game_id,
                board=None,  # type: ignore
                status=GameStatus.NOT_STARTED,
                flags_used=0,
                cells_revealed=0
            )
        return self.game_state
