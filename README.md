## Frontend

This project provides a template for running Python applications in the browser with minimal JavaScript configuration. The frontend architecture allows developers to focus solely on writing Python code in `client.py`, while the underlying JavaScript infrastructure handles browser integration, terminal display, and Python environment management.

### Core Philosophy

The template separates concerns into two distinct areas:
- **Infrastructure** (`terminal.js`, `pyodideWorker.js`): Handles all browser/JavaScript requirements
- **Application** (`client.py`): Where developers write pure Python code

This separation means you can create new browser-based Python applications by:
1. Copying the template
2. Replacing only `client.py` with your Python code
3. Leaving the JavaScript infrastructure untouched

### Core Components

#### Terminal Interface (`terminal.js`)
- Creates an xterm.js terminal instance with custom styling and input handling
- Manages the terminal UI, cursor states, and user input buffer
- Implements a custom loading animation with real-time progress feedback
- Handles message routing between the terminal UI and Python environment
- Requires no modification for new applications

#### Python Worker (`pyodideWorker.js`)
- Runs Pyodide in a WebWorker to prevent blocking the main thread
- Initializes the Python environment with custom print/input functions
- Manages package loading and Python code execution
- Handles bidirectional communication with the main thread
- Serves as a reusable component across different Python applications

#### Message Types (`messageTypes.js`)
- Defines the communication protocol between terminal and worker
- Provides message type constants to ensure consistency
- Implements message handling and validation
- Centralizes message routing logic
- Acts as a single source of truth for system messages

### Python Development Experience

The template provides a native Python development experience in the browser:

- **Standard I/O**: Use regular `print()` and `input()` functions as you would in any Python application
- **Package Support**: Access to Python packages through micropip
- **Async Support**: Built-in support for asyncio and async/await syntax
- **Error Handling**: Python exceptions are properly caught and displayed in the terminal
- **HTTP Capabilities**: Includes pyodide-http for making network requests

### Template Usage

To create a new Python browser application:

1. Clone/copy the template
2. Keep all files except `client.py`
3. Create your new `client.py` with these requirements:
   - Must include an async `main()` function as the entry point
   - Can use standard Python syntax and features
   - Can make network requests using standard Python libraries
   - Can use `print()` and `input()` for terminal interaction

The template handles all browser integration automatically, allowing developers to focus purely on Python application logic.

### Design Considerations

- Completely separates Python application code from browser integration code
- Provides familiar Python development experience
- Handles all browser-specific complexities behind the scenes
- Maintains consistent terminal experience across different applications
- Ensures proper resource management and error handling