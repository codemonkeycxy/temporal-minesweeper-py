"""Flask server for Minesweeper game."""
import asyncio
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from temporalio.client import Client
import uuid

from src.workflows import MinesweeperWorkflow
from src.types import GameConfig, MoveRequest
from src.client_provider import get_temporal_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../public')
CORS(app)

# Global client reference
temporal_client: Client | None = None


def serialize_datetime(obj):
    """Helper to serialize datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def serialize_game_state(game_state):
    """Convert game state to JSON-serializable format."""
    if not game_state:
        return None

    # Handle both dict and object access
    def get_attr(obj, key):
        """Get attribute from either dict or object."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    # Convert cells to dictionaries
    cells = []
    board = get_attr(game_state, 'board')
    if board:
        board_cells = get_attr(board, 'cells')
        if board_cells:
            for row in board_cells:
                row_cells = []
                for cell in row:
                    row_cells.append({
                        'isMine': get_attr(cell, 'is_mine'),
                        'isRevealed': get_attr(cell, 'is_revealed'),
                        'isFlagged': get_attr(cell, 'is_flagged'),
                        'neighborMines': get_attr(cell, 'neighbor_mines'),
                        'row': get_attr(cell, 'row'),
                        'col': get_attr(cell, 'col')
                    })
                cells.append(row_cells)

    status = get_attr(game_state, 'status')
    start_time = get_attr(game_state, 'start_time')
    end_time = get_attr(game_state, 'end_time')

    # Ensure status is always a string - be very explicit
    logger.debug(f"Raw status before conversion: {repr(status)} (type: {type(status)})")

    if isinstance(status, (list, tuple)):
        # If it's a list/tuple, join it
        status_str = ''.join(str(c) for c in status).upper()
        logger.warning(f"Status was a list/tuple: {status}, converted to: {status_str}")
    elif hasattr(status, 'value'):
        status_str = str(status.value).upper()
    elif hasattr(status, 'name'):
        status_str = str(status.name).upper()
    elif isinstance(status, str):
        status_str = status.upper()
    else:
        status_str = str(status).upper() if status else 'NOT_STARTED'

    logger.info(f"Final status: {status_str}")

    return {
        'id': get_attr(game_state, 'id'),
        'board': {
            'cells': cells,
            'width': get_attr(board, 'width') if board else 0,
            'height': get_attr(board, 'height') if board else 0,
            'mineCount': get_attr(board, 'mine_count') if board else 0
        },
        'status': status_str,
        'startTime': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
        'endTime': end_time.isoformat() if isinstance(end_time, datetime) else end_time,
        'flagsUsed': get_attr(game_state, 'flags_used'),
        'cellsRevealed': get_attr(game_state, 'cells_revealed')
    }


async def query_with_retry(handle, query_name, max_retries=5):
    """Query with retry logic for workflow initialization."""
    for i in range(max_retries):
        try:
            return await handle.query(query_name)
        except Exception as error:
            if i < max_retries - 1:
                logger.info(f"Query not ready yet, retrying in {(i + 1) * 100}ms...")
                await asyncio.sleep((i + 1) * 0.1)
                continue
            raise error


@app.route('/api/games', methods=['POST'])
def create_game():
    """Create a new game."""
    try:
        data = request.json
        config_data = data.get('config')

        # Validate config
        if not config_data or 'width' not in config_data or 'height' not in config_data or 'mineCount' not in config_data:
            return jsonify({'error': 'Invalid game configuration'}), 400

        config = GameConfig(
            width=config_data['width'],
            height=config_data['height'],
            mine_count=config_data['mineCount']
        )

        if config.mine_count >= config.width * config.height:
            return jsonify({'error': 'Too many mines for the board size'}), 400

        game_id = str(uuid.uuid4())

        # Start the workflow
        async def start_workflow():
            await temporal_client.start_workflow(
                MinesweeperWorkflow.run,
                args=[game_id, config],
                id=game_id,
                task_queue="minesweeper-task-queue"
            )

            # Get initial game state with retry
            handle = temporal_client.get_workflow_handle(game_id)
            game_state = await query_with_retry(handle, "get_game_state_query")
            return game_state

        game_state = asyncio.run(start_workflow())
        return jsonify({'gameState': serialize_game_state(game_state)})

    except Exception as error:
        logger.error(f"Error creating game: {error}")
        return jsonify({'error': 'Failed to create game'}), 500


@app.route('/api/games/<game_id>', methods=['GET'])
def get_game_state(game_id):
    """Get game state."""
    try:
        async def query_game():
            handle = temporal_client.get_workflow_handle(game_id)
            game_state = await query_with_retry(handle, "get_game_state_query")
            return game_state

        game_state = asyncio.run(query_game())
        return jsonify({'gameState': serialize_game_state(game_state)})

    except Exception as error:
        logger.error(f"Error getting game state: {error}")
        return jsonify({'error': 'Game not found'}), 404


@app.route('/api/games/<game_id>/moves', methods=['POST'])
def make_move(game_id):
    """Make a move."""
    try:
        data = request.json

        # Validate move request
        if not isinstance(data.get('row'), int) or \
           not isinstance(data.get('col'), int) or \
           data.get('action') not in ['reveal', 'flag', 'unflag', 'chord']:
            return jsonify({'error': 'Invalid move request'}), 400

        move_request = MoveRequest(
            row=data['row'],
            col=data['col'],
            action=data['action']
        )

        async def execute_move():
            handle = temporal_client.get_workflow_handle(game_id)
            # Execute move update and get the updated state directly
            game_state = await handle.execute_update(
                "make_move_update",
                move_request
            )
            return game_state

        game_state = asyncio.run(execute_move())
        serialized = serialize_game_state(game_state)
        return jsonify({'gameState': serialized})

    except Exception as error:
        logger.error(f"Error making move: {error}")
        return jsonify({'error': 'Failed to make move'}), 500


@app.route('/api/games/<game_id>/restart', methods=['POST'])
def restart_game(game_id):
    """Restart game."""
    try:
        data = request.json
        config_data = data.get('config')

        # Validate config
        if not config_data or 'width' not in config_data or 'height' not in config_data or 'mineCount' not in config_data:
            return jsonify({'error': 'Invalid game configuration'}), 400

        config = GameConfig(
            width=config_data['width'],
            height=config_data['height'],
            mine_count=config_data['mineCount']
        )

        async def execute_restart():
            handle = temporal_client.get_workflow_handle(game_id)
            # Execute restart update and get the updated state directly
            game_state = await handle.execute_update(
                "restart_game_update",
                config
            )
            return game_state

        game_state = asyncio.run(execute_restart())
        return jsonify({'gameState': serialize_game_state(game_state)})

    except Exception as error:
        logger.error(f"Error restarting game: {error}")
        return jsonify({'error': 'Failed to restart game'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/')
def index():
    """Serve the frontend."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory(app.static_folder, path)


async def initialize_client():
    """Initialize Temporal client."""
    global temporal_client
    temporal_client = await get_temporal_client()
    logger.info("Connected to Temporal server")


def main():
    """Start the Flask server."""
    try:
        # Initialize Temporal client
        asyncio.run(initialize_client())

        port = int(os.getenv("PORT", 3000))
        logger.info(f"Minesweeper server running on http://localhost:{port}")
        logger.info("Make sure to start the Temporal worker in another terminal: python -m src.worker")

        app.run(host='0.0.0.0', port=port, debug=False)

    except Exception as error:
        logger.error(f"Failed to start server: {error}")
        exit(1)


if __name__ == "__main__":
    main()
