class PyTerminal {
    constructor(options = {}) {
        this.terminalOptions = {
            rows: 24,
            cols: 80,
            cursorBlink: true,
            scrollback: 1000,
            disableStdin: false,
            rendererType: "canvas",
            theme: {
                background: '#000000',
                foreground: '#ffffff'
            },
            allowTransparency: true,
            convertEol: true,
            wordWrap: true,
            windowsMode: false,
            wraparoundMode: true,
            ...options
        };

        this.term = null;
        this.addons = {
            fit: new FitAddon.FitAddon(),
            webLinks: new WebLinksAddon.WebLinksAddon(),
            webgl: new WebglAddon.WebglAddon()
        };
        this.inputBuffer = '';
        this.inputResolve = null;
        this.pyodide = null;
    }

    termWrite(text, color = null) {
        const colors = {
            'green': '\u001b[92m',
            'gray': '\u001b[2;90m',      // Dimmed gray
            'red': '\u001b[31m',
            'white': '\u001b[37m'        // Regular white (no dimming)
        };

        if (color && colors[color]) {
            this.term.write(`${colors[color]}${text}\u001b[0m`);
        } else {
            this.term.write(text);
        }
    }

    async initialize(containerId, pythonScript = '/client.py') {
        // Initialize terminal
        this.term = new Terminal(this.terminalOptions);
        window.term = this.term;
        this.term.open(document.getElementById(containerId));

        // Hide cursor initially and focus the terminal
        this.term.write('\x1b[?25l');
        this.term.focus();

        this._initializeTerminal();

        // Initialize Pyodide environment
        await this._initializePyodide(pythonScript);
    }

    _initializeTerminal() {
        // Load addons
        for (const [name, addon] of Object.entries(this.addons)) {
            try {
                this.term.loadAddon(addon);
            } catch (e) {
                console.warn(`${name} addon failed to load:`, e);
            }
        }

        this.addons.fit.fit();
        window.addEventListener('resize', () => this.addons.fit.fit());

        // Setup input handling
        this.term.onKey(({ key, domEvent }) => {
            const keyHandlers = {
                13: () => this._handleEnterKey(),    // Enter
                8: () => this._handleBackspace(),     // Backspace
                default: () => this._handleRegularInput(key)
            };

            (keyHandlers[domEvent.keyCode] || keyHandlers.default)();
        });
    }

    async dotLoad(msg, op, ms = 1000) {
        /*
         * Shows animated dots (...) while awaiting an async operation
         * Usage: await this.dotLoad('Loading', fetchData(), 500);
         * @msg: text to show  @op: promise to await  @ms: dot speed
         */
        this.termWrite(msg, 'white');
        this.term.write('\u001b7');

        let dots = 0;
        const animation = setInterval(() => {
            this.term.write('\u001b8');
            this.termWrite('.'.repeat(dots = (dots + 1) % 4), 'white');
        }, ms);

        // Trigger first animation frame immediately
        this.term.write('\u001b8');
        this.termWrite('', 'white');

        const waitForThreeDots = () => new Promise(r => {
            const check = setInterval(() => {
                if (dots === 3) {
                    clearInterval(check);
                    r();
                }
            }, 50);
        });

        try {
            const result = await op;
            await waitForThreeDots();
            clearInterval(animation);
            this.term.write('\u001b8');
            this.termWrite('...\n\n', 'white');
            return result;
        } catch (error) {
            clearInterval(animation);
            this.term.write('\u001b8');
            this.termWrite('...\n\n', 'red');
            throw error;
        }
    }

    async _initializePyodide(pythonScript) {
        try {
            const pageTitle = document.title || 'Terminal';
            this.pyodide = await this.dotLoad(
                `Loading ${pageTitle}`,
                loadPyodide({
                    stdout: (text) => this.termWrite(text + '\n', 'gray'),
                    stderr: (text) => this.termWrite(text + '\n', 'red')
                })
            );

            // Set up basic globals
            this.pyodide.globals.set('term', this.term);
            this.pyodide.globals.set('get_input', this.getInput.bind(this));

            // Load required packages
            await this.pyodide.loadPackage('micropip');
            await this.pyodide.runPythonAsync(`
                import sys
                import asyncio
                import builtins
                import codecs
                import urllib.request  # Python's built-in HTTP module
                from js import term, window
                
                # Configure custom input/output
                def setupIO():
                    async def custom_input(prompt=''):
                        return await get_input(prompt)
                    builtins.input = custom_input
                    
                    def custom_print(text):
                        window.term.write(text)
                    builtins.print = custom_print
    
                    # Create a pythonic decoder interface
                    class StreamDecoder:
                        @staticmethod
                        def new(encoding):
                            decoder = window.TextDecoder.new(encoding)
                            return decoder
                    
                    # Add it to codecs module
                    codecs.StreamDecoder = StreamDecoder
                
                # Install and configure required packages
                async def setupPackages():
                    import micropip
                    required_packages = ['pyodide-http']
                    await asyncio.gather(*[micropip.install(pkg) for pkg in required_packages])
                    import pyodide_http
                    pyodide_http.patch_all()
                    
                    # Add pyfetch to urllib.request
                    from pyodide.http import pyfetch
                    urllib.request.fetch = pyfetch
                
                # Run setup functions
                setupIO()
                await setupPackages()
            `);

            // Load and run the Python application
            const response = await fetch(pythonScript);
            const pythonCode = await response.text();
            await this.pyodide.runPythonAsync(pythonCode);
            await this.pyodide.runPythonAsync('asyncio.ensure_future(main())');
        } catch (error) {
            this.termWrite('Error initializing Python environment:\n', 'red');
            this.termWrite(error.toString() + '\n', 'red');
            throw error;
        }
    }

    _handleEnterKey() {
        this.term.writeln('');
        if (this.inputResolve) {
            const response = this.inputBuffer;
            this.inputBuffer = '';
            const resolve = this.inputResolve;
            this.inputResolve = null;

            // Hide cursor after input
            this.term.write('\x1b[?25l');

            resolve(response);
        }
    }

    _handleBackspace() {
        if (this.inputBuffer.length > 0) {
            this.inputBuffer = this.inputBuffer.slice(0, -1);
            this.term.write('\b \b');
        }
    }

    _handleRegularInput(key) {
        this.inputBuffer += key;
        this.term.write(key);
    }

    async getInput(prompt) {
        // Show cursor before input
        this.term.write('\x1b[?25h');
        this.termWrite(prompt);

        try {
            return await new Promise((resolve) => {
                this.inputResolve = resolve;
            });
        } finally {
            // Hide cursor after input is complete
            this.term.write('\x1b[?25l');
        }
    }
}

// Initialize terminal when the script loads
const pyTerminal = new PyTerminal();
pyTerminal.initialize('terminal').catch(console.error);