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

    async initialize(containerId) {
        this.term = new Terminal(this.terminalOptions);
        window.term = this.term;

        this.term.open(document.getElementById(containerId));
        this._initializeTerminal();
        await this._initializePyodide();
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
                8: () => this._handleBackspace(),    // Backspace
                default: () => this._handleRegularInput(key)
            };

            (keyHandlers[domEvent.keyCode] || keyHandlers.default)();
        });
    }

    async _initializePyodide() {
        this.term.writeln('\u001b[90mInitializing...\u001b[0m');

        try {
            this.pyodide = await loadPyodide({
                stdout: (text) => this.term.writeln(`\u001b[90m${text}\u001b[0m`),
                stderr: (text) => this.term.writeln(`\u001b[31m${text}\u001b[0m`)
            });

            // Set up globals
            this.pyodide.globals.set('term', this.term);
            this.pyodide.globals.set('TextDecoder', window.TextDecoder);
            this.pyodide.globals.set('get_input', this.getInput.bind(this));

            // Setup custom input handler
            await this.pyodide.runPython(`
            import builtins
            async def custom_input(prompt=''):
              return await get_input(prompt)
            builtins.input = custom_input
          `);

            // Load micropip once and configure all package installations
            await this.pyodide.loadPackage('micropip');

            // Install only required packages
            await this.pyodide.runPythonAsync(`
            import micropip
            import asyncio
            
            required_packages = [
              'pyodide-http',
              'PyPDF2'
            ]
            
            await asyncio.gather(
              *[micropip.install(pkg) for pkg in required_packages]
            )
            
            import pyodide_http
            pyodide_http.patch_all()
          `);

            // this.term.writeln('\u001b[90mPython environment ready\u001b[0m');
            // Load and run main Python code
            const response = await fetch('/client.py');
            const pythonCode = await response.text();
            await this.pyodide.runPythonAsync(pythonCode);
            await this.pyodide.runPythonAsync('asyncio.ensure_future(main())');


        } catch (error) {
            this.term.writeln('\u001b[31mError initializing Python environment:\u001b[0m');
            this.term.writeln(`\u001b[31m${error.toString()}\u001b[0m`);
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
        this.term.write(prompt);
        return new Promise((resolve) => {
            this.inputResolve = resolve;
        });
    }
}

// Usage
const pyTerminal = new PyTerminal();
pyTerminal.initialize('terminal').catch(console.error);