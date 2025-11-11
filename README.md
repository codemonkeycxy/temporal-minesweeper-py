# Temporal Minesweeper 🚩

A modern Minesweeper game built with **Temporal Workflows** for state management, featuring a web-based UI and REST API backend - Python edition.

## Architecture Overview

This application demonstrates the power of Temporal workflows for game state management:

- **Temporal Workflows**: Each game instance runs as a long-lived workflow that maintains game state in memory
- **Activities**: Pure functions for game logic (board creation, cell revealing, flag toggling)
- **Signals**: Used to send moves to the workflow (reveal, flag, unflag, restart)
- **Queries**: Used to retrieve current game state from the workflow
- **REST API**: Flask server that interfaces with Temporal workflows
- **Frontend**: Modern HTML/CSS/JavaScript interface

## Features

- 🎮 Classic Minesweeper gameplay
- 🌐 Web-based interface with modern UI
- ⚡ Real-time game state updates
- 🔧 Configurable difficulty levels (Beginner, Intermediate, Expert, Custom)
- ⏱️ Game timer and statistics
- 🏃‍♂️ Powered by Temporal workflows (no database required!)
- 📱 Responsive design for mobile and desktop

## Prerequisites

- **Python** (v3.9 or higher)
- **Temporal Server** (see installation instructions below)

## Quick Start

### 1. Install Temporal CLI and Start Server

```bash
# Install Temporal CLI
brew install temporal

# Start Temporal server (in background)
temporal server start-dev
```

The Temporal Web UI will be available at http://localhost:8233

### 1a. Configuration (Optional)

The application can connect to Temporal in two ways:

**Option 1: Environment Variables (default)**
```bash
# Optional - defaults to localhost:7233 and "default" namespace
export TEMPORAL_ADDRESS="localhost:7233"
export TEMPORAL_NAMESPACE="default"
```

**Option 2: Configuration Profile (for Temporal Cloud)**
```bash
# Set the profile name (reads from temporal.toml config file)
export TEMPORAL_PROFILE="my-cloud-profile"
```

The config file location is platform-specific:
- **macOS**: `~/Library/Application Support/temporalio/temporal.toml`
- **Linux**: `~/.config/temporalio/temporal.toml` (or `$XDG_CONFIG_HOME/temporalio/temporal.toml`)
- **Windows**: `%AppData%\temporalio\temporal.toml`

This allows seamless integration with Temporal Cloud or custom Temporal deployments.

### 2. Start the Application

The `start.sh` script will automatically:
- Create a virtual environment (if it doesn't exist)
- Install dependencies
- Start both the Temporal worker and web server

```bash
chmod +x start.sh
./start.sh
```

Alternatively, you can run components manually:

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Terminal 1: Start the Temporal worker
python -m src.worker

# Terminal 2: Start the web server
python -m src.server
```

### 3. Play the Game!

Open your browser and navigate to:
```
http://localhost:3000
```

## Game Controls

- **Left Click**: Reveal a cell
- **Right Click**: Toggle flag on a cell
- **Double Click**: Mass open adjacent cells (chord - when flags match the number)
- **Goal**: Reveal all cells that don't contain mines
- **Numbers**: Show the count of neighboring mines

## API Endpoints

The application provides the following REST API endpoints:

### Create New Game
```http
POST /api/games
Content-Type: application/json

{
  "config": {
    "width": 9,
    "height": 9,
    "mineCount": 10
  }
}
```

### Get Game State
```http
GET /api/games/{gameId}
```

### Make a Move
```http
POST /api/games/{gameId}/moves
Content-Type: application/json

{
  "row": 0,
  "col": 0,
  "action": "reveal" | "flag" | "unflag" | "chord"
}
```

### Restart Game
```http
POST /api/games/{gameId}/restart
Content-Type: application/json

{
  "config": {
    "width": 9,
    "height": 9,
    "mineCount": 10
  }
}
```

### Health Check
```http
GET /api/health
```

## How Temporal Powers the Game

### Workflows
Each game runs as a Temporal workflow (`MinesweeperWorkflow`) that:
- Maintains game state in memory (no database needed!)
- Handles game operations through signals and updates
- Provides game state through queries
- Runs indefinitely until manually terminated or after 24 hours of inactivity

### Activities
Game logic is implemented as Temporal activities:
- `create_game_board`: Generates a new board with randomly placed mines
- `reveal_cell`: Handles cell revelation with cascade logic
- `toggle_flag`: Manages flag placement and removal
- `chord_reveal`: Mass opens adjacent cells when flags match the number

### Signals & Updates
Game operations are sent as signals or updates to the workflow:
- `make_move_signal`: Fire-and-forget move signal
- `make_move_update`: Move update that returns updated state
- `restart_game_signal`: Fire-and-forget restart signal
- `restart_game_update`: Restart update that returns new state

### Queries
Current game state is retrieved using queries:
- `get_game_state_query`: Returns the current state of the game

## Project Structure

```
├── src/
│   ├── __init__.py       # Package initialization
│   ├── types.py          # Type definitions
│   ├── client_provider.py # Temporal client configuration
│   ├── activities.py     # Temporal activities (game logic)
│   ├── workflows.py      # Temporal workflows
│   ├── worker.py         # Temporal worker
│   └── server.py         # Flask REST API server
├── public/
│   ├── index.html        # Game interface
│   ├── styles.css        # Styling
│   └── script.js         # Frontend JavaScript
├── requirements.txt      # Python dependencies
├── start.sh             # Convenience script to start worker and server
└── README.md            # This file
```

## Customization

You can customize the game by modifying:

- **Difficulty levels**: Edit the configs in `public/script.js`
- **Game logic**: Modify activities in `src/activities.py`
- **UI styling**: Update `public/styles.css`
- **API endpoints**: Extend `src/server.py`

## Temporal Web UI

Monitor your game workflows in the Temporal Web UI at http://localhost:8233. You can:
- View running workflows (active games)
- Inspect workflow history and events
- See signal and query operations
- Debug workflow executions

## Troubleshooting

### Temporal Server Issues
- Make sure Temporal server is running: `temporal server start-dev`
- Check if port 7233 is available
- Verify Temporal CLI installation

### Build Issues
- Ensure Python 3.9+ is installed: `python --version`
- Check virtual environment is activated
- Try reinstalling dependencies: `pip install -r requirements.txt`

### Game Not Loading
- Check browser console for errors
- Verify both worker and server are running
- Ensure Temporal server is accessible

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - feel free to use this project for learning and experimentation!

---

**Happy Mining!** 🚩💣
