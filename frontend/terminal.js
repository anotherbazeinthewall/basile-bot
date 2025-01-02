class PyTerminal {
    constructor(options = {}) {
        this.terminalOptions = {
            rows: 24, cols: 80, cursorBlink: true, scrollback: 1000,
            disableStdin: false, rendererType: "canvas",
            theme: { background: '#000000', foreground: '#d4d7cd' },
            allowTransparency: true, convertEol: true, wordWrap: true,
            windowsMode: false, wraparoundMode: true, ...options
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
        this.messageHandler = new MessageHandler();
        this._initializeMessageHandlers();
    }

    _initializeMessageHandlers() {
        const handlers = {
            [MessageTypes.STDOUT]: ({ text }) => text && this.term.write(text),
            [MessageTypes.STDERR]: ({ text }) => text && this.term.write(text),
            [MessageTypes.INPUT]: async ({ prompt, id }) => {
                try {
                    const response = await this.getInput(prompt);
                    this.pyodide.postMessage({ type: MessageTypes.INPUT_RESPONSE, value: response, id });
                } catch (error) { console.error('Input error:', error); }
            },
            [MessageTypes.LOADED]: () => { },
            [MessageTypes.PACKAGE_LOADED]: () => { },
            [MessageTypes.PYTHON_READY]: () => { },
            [MessageTypes.ERROR]: ({ error, stack }) => {
                console.error('Pyodide error:', error, stack);
                this.term.write(`Error: ${error}\n`);
            }
        };

        Object.entries(handlers).forEach(([type, handler]) =>
            this.messageHandler.register(type, handler));
    }

    async initialize(containerId, pythonScript = '/client.py') {
        this.term = new Terminal(this.terminalOptions);
        window.term = this.term;
        this.term.open(document.getElementById(containerId));
        this.term.write('\x1b[?25l');
        this.term.focus();
        this._initializeTerminal();
        await this._initializePyodide(pythonScript);
    }

    _initializeTerminal() {
        Object.entries(this.addons).forEach(([name, addon]) => {
            try {
                this.term.loadAddon(addon);
            } catch (e) {
                console.warn(`${name} addon failed to load:`, e);
            }
        });

        this.addons.fit.fit();
        window.addEventListener('resize', () => this.addons.fit.fit());

        this.term.onKey(({ key, domEvent }) => {
            const keyHandlers = {
                13: () => this._handleEnterKey(),
                8: () => this._handleBackspace(),
                default: () => this._handleRegularInput(key)
            };
            (keyHandlers[domEvent.keyCode] || keyHandlers.default)();
        });
    }

    async dotLoad(msg, ms = 750) {
        console.log(`[${performance.now().toFixed(2)}ms] Starting dotLoad...`);
        const startTime = performance.now();

        this.term.write(msg);
        this.term.write('\u001b7');
        let dots = 0;
        let animationInterval;
        let isResolved = false;
        let resolvePromise;

        console.log(`[${(performance.now() - startTime).toFixed(2)}ms] Creating worker...`);
        const worker = new Worker('pyodideWorker.js');
        const pyodidePromise = new Promise((resolve, reject) => {
            resolvePromise = resolve;
            worker.onmessage = async (event) => {
                await this.messageHandler.handle(event.data);
                if (event.data.type === MessageTypes.LOADED) {
                    const resolveTime = performance.now() - startTime;
                    console.log(`[${resolveTime.toFixed(2)}ms] Pyodide loaded`);
                    isResolved = true;
                }
            };
            worker.onerror = (error) => reject(error);
        });

        console.log(`[${(performance.now() - startTime).toFixed(2)}ms] Sending LOAD message to worker...`);
        worker.postMessage({ type: MessageTypes.LOAD });

        const animate = () => {
            const currentTime = performance.now() - startTime;
            console.log(`[${currentTime.toFixed(2)}ms] Animation frame ${dots}`);

            if (!isResolved) {
                this.term.write('\u001b8');
                this.term.write(' '.repeat(3));
                this.term.write('\u001b8');
                this.term.write('.'.repeat(dots));
                dots = (dots + 1) % 4;
            } else {
                console.log(`[${currentTime.toFixed(2)}ms] Animation complete`);
                clearInterval(animationInterval);
                this.term.write('\u001b8');
                this.term.write('...\n\n');
                resolvePromise(worker);
            }
        };

        console.log(`[${(performance.now() - startTime).toFixed(2)}ms] Starting animation...`);
        animate();
        animationInterval = setInterval(animate, ms);

        try {
            const result = await pyodidePromise;
            console.log(`[${(performance.now() - startTime).toFixed(2)}ms] dotLoad complete`);
            return result;
        } catch (error) {
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

            if (!this.pyodide) {
                this.pyodide = await this.dotLoad(`Loading ${pageTitle}`);
                this.pyodide.onmessage = async (event) => {
                    await this.messageHandler.handle(event.data);
                };
            }

            const createPromise = (expectedType) => new Promise((resolve, reject) => {
                const handler = (event) => {
                    if (event.data.type === expectedType) {
                        this.pyodide.removeEventListener('message', handler);
                        resolve();
                    } else if (event.data.type === MessageTypes.ERROR) {
                        this.pyodide.removeEventListener('message', handler);
                        reject(new Error(event.data.error));
                    }
                };
                this.pyodide.addEventListener('message', handler);
            });

            // Load and run Python script
            const pythonCode = await (await fetch(pythonScript)).text();
            this.pyodide.postMessage({ type: MessageTypes.RUN_PYTHON, args: [pythonCode] });
            await createPromise(MessageTypes.PYTHON_READY);

            this.pyodide.postMessage({ type: MessageTypes.RUN_PYTHON, args: ['asyncio.ensure_future(main())'] });
            await createPromise(MessageTypes.PYTHON_READY);

        } catch (error) {
            this.term.write(`Error initializing Python environment:\n${error}\n`);
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
        this.term.write('\x1b[?25h');
        this.term.write(prompt);
        try {
            return await new Promise(resolve => { this.inputResolve = resolve; });
        } finally {
            this.term.write('\x1b[?25l');
        }
    }
}

const pyTerminal = new PyTerminal();
pyTerminal.initialize('terminal').catch(console.error);