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
                foreground: '#d4d7cd'  // Using the dimmer white (212,215,205)
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

    async dotLoad(msg, pageTitle, ms = 500) {
        const startTime = performance.now();
        console.log('Initial message at 0ms');
        this.term.write(msg);
        this.term.write('\u001b7'); // Save cursor position

        let dots = 0;
        let animationInterval;
        let isResolved = false;
        let resolvePromise;

        // Initialize the Web Worker
        const worker = new Worker('pyodideWorker.js');

        // Create a promise to handle worker messages
        const pyodidePromise = new Promise((resolve, reject) => {
            resolvePromise = resolve;
            worker.onmessage = async (event) => {
                const { type, text, error, prompt } = event.data;

                switch (type) {
                    case 'stdout':
                        this.term.write(text);
                        break;
                    case 'stderr':
                        this.term.write(text);
                        break;
                    case 'loaded':
                        const resolveTime = performance.now() - startTime;
                        console.log(`Promise resolved at ${resolveTime.toFixed(2)}ms`);
                        isResolved = true;
                        break;
                    case 'input':
                        const response = await this.getInput(prompt);
                        worker.postMessage({ type: 'inputResponse', value: response });
                        break;
                    case 'error':
                        reject(new Error(error));
                        break;
                }
            };

            worker.onerror = (error) => {
                reject(error);
            };
        });

        // Start the worker
        worker.postMessage({ type: 'load' });

        // Animation function
        const animate = () => {
            const currentTime = performance.now() - startTime;
            console.log(`Dot animation ${dots} at ${currentTime.toFixed(2)}ms`);

            this.term.write('\u001b8'); // Restore cursor position
            this.term.write('   '); // Clear previous dots
            this.term.write('\u001b8'); // Restore cursor position again
            this.term.write('.'.repeat(dots));

            dots = (dots + 1) % 4;

            if (isResolved && dots === 0) {
                clearInterval(animationInterval);
                console.log(`Animation completed at ${currentTime.toFixed(2)}ms`);
                this.term.write('\u001b8');
                this.term.write('...\n\n');

                resolvePromise({
                    worker,
                    loadPackage: async (...args) => {
                        return new Promise((resolve, reject) => {
                            worker.onmessage = (event) => {
                                if (event.data.type === 'loadPackage') {
                                    resolve(event.data.result);
                                } else if (event.data.type === 'error') {
                                    reject(new Error(event.data.error));
                                }
                            };
                            worker.postMessage({ type: 'loadPackage', args });
                        });
                    },
                    runPythonAsync: async (...args) => {
                        return new Promise((resolve, reject) => {
                            worker.onmessage = (event) => {
                                if (event.data.type === 'runPython') {
                                    resolve(event.data.result);
                                } else if (event.data.type === 'error') {
                                    reject(new Error(event.data.error));
                                }
                            };
                            worker.postMessage({ type: 'runPython', args });
                        });
                    }
                });
            }
        };

        // Start the animation immediately
        animate();
        animationInterval = setInterval(animate, ms);

        try {
            return await pyodidePromise;
        } catch (error) {
            const currentTime = performance.now() - startTime;
            console.log(`Error occurred at ${currentTime.toFixed(2)}ms`);
            clearInterval(animationInterval);
            this.term.write('\u001b8');
            this.term.write('...\n\n');
            worker.terminate();
            throw error;
        }
    }

    async _initializePyodide(pythonScript) {
        try {
            const pageTitle = document.title || 'Terminal';

            // Initialize the Web Worker
            if (!this.pyodide) {
                this.pyodide = new Worker('pyodideWorker.js');

                // Set up message handling
                this.pyodide.onmessage = async (event) => {
                    const { type, text, prompt, id } = event.data;

                    switch (type) {
                        case 'stdout':
                            if (text) this.term.write(text);
                            break;
                        case 'stderr':
                            if (text) this.term.write(text);
                            break;
                        case 'input':
                            try {
                                const response = await this.getInput(prompt);
                                this.pyodide.postMessage({
                                    type: 'inputResponse',
                                    value: response,
                                    id
                                });
                            } catch (error) {
                                console.error('Input error:', error);
                            }
                            break;
                    }
                };
            }

            // Initialize Pyodide with loading animation
            await this.dotLoad(
                `Loading ${pageTitle}`,
                pageTitle,
                500
            );

            // Wait for initial load to complete
            await new Promise((resolve, reject) => {
                const handler = (event) => {
                    if (event.data.type === 'loaded') {
                        this.pyodide.removeEventListener('message', handler);
                        resolve();
                    } else if (event.data.type === 'error') {
                        this.pyodide.removeEventListener('message', handler);
                        reject(new Error(event.data.error));
                    }
                };

                this.pyodide.addEventListener('message', handler);
                this.pyodide.postMessage({ type: 'load' });
            });

            // Load required packages
            await new Promise((resolve, reject) => {
                const handler = (event) => {
                    if (event.data.type === 'loadPackage') {
                        this.pyodide.removeEventListener('message', handler);
                        resolve();
                    } else if (event.data.type === 'error') {
                        this.pyodide.removeEventListener('message', handler);
                        reject(new Error(event.data.error));
                    }
                };

                this.pyodide.addEventListener('message', handler);
                this.pyodide.postMessage({
                    type: 'loadPackage',
                    args: ['micropip']
                });
            });

            // Load and run the Python script
            const response = await fetch(pythonScript);
            const pythonCode = await response.text();

            await new Promise((resolve, reject) => {
                const handler = (event) => {
                    if (event.data.type === 'runPython') {
                        this.pyodide.removeEventListener('message', handler);
                        resolve();
                    } else if (event.data.type === 'error') {
                        this.pyodide.removeEventListener('message', handler);
                        reject(new Error(event.data.error));
                    }
                };

                this.pyodide.addEventListener('message', handler);
                this.pyodide.postMessage({
                    type: 'runPython',
                    args: [pythonCode]
                });
            });

            // Start the main function
            await new Promise((resolve, reject) => {
                const handler = (event) => {
                    if (event.data.type === 'runPython') {
                        this.pyodide.removeEventListener('message', handler);
                        resolve();
                    } else if (event.data.type === 'error') {
                        this.pyodide.removeEventListener('message', handler);
                        reject(new Error(event.data.error));
                    }
                };

                this.pyodide.addEventListener('message', handler);
                this.pyodide.postMessage({
                    type: 'runPython',
                    args: ['asyncio.ensure_future(main())']
                });
            });

        } catch (error) {
            this.term.write('Error initializing Python environment:\n');
            this.term.write(error.toString() + '\n');
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
        this.term.write(prompt);

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