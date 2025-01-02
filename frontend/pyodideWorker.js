self.MessageTypes = {
    STDOUT: 'stdout', STDERR: 'stderr', INPUT: 'input', INPUT_RESPONSE: 'inputResponse',
    LOAD: 'load', LOADED: 'loaded', LOAD_PACKAGE: 'loadPackage', PACKAGE_LOADED: 'packageLoaded',
    RUN_PYTHON: 'runPython', PYTHON_READY: 'pythonReady', ERROR: 'error'
};

class MessageHandler {
    constructor() { this.handlers = new Map(); }
    register(messageType, handler) { this.handlers.set(messageType, handler); }
    async handle(message) {
        const handler = this.handlers.get(message.type);
        if (handler) return await handler(message);
        throw new Error(`No handler for: ${message.type}`);
    }
}

self.importScripts('https://cdn.jsdelivr.net/pyodide/v0.23.0/full/pyodide.js');
let pyodide = null;
let initializePromise = null;
let inputResolvers = new Map();
let messageId = 0;

const messageHandler = new MessageHandler();
const safePostMessage = (type, data = {}) => self.postMessage({ type, ...data });

async function initializePyodide() {
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
        pyodide = await loadPyodide({
            stdout: text => safePostMessage(MessageTypes.STDOUT, { text }),
            stderr: text => safePostMessage(MessageTypes.STDERR, { text })
        });

        self.terminal = { write: text => safePostMessage(MessageTypes.STDOUT, { text: String(text) }) };
        self.input = prompt => new Promise(resolve => {
            const id = messageId++;
            inputResolvers.set(id, resolve);
            safePostMessage(MessageTypes.INPUT, { prompt, id });
        });

        // Load required packages and set up Python environment
        await pyodide.loadPackage(['micropip']);

        await pyodide.runPythonAsync(`
            import sys, asyncio, builtins, codecs, urllib.request
            from pyodide.ffi import create_proxy
            from js import self

            def custom_print(*args, sep=' ', end='\\n', file=None):
                self.terminal.write(sep.join(str(arg) for arg in args))

            async def custom_input(prompt=''): return await self.input(prompt)

            builtins.print = custom_print
            builtins.input = custom_input

            class StreamDecoderClass:
                @staticmethod
                def new(encoding): return self.TextDecoder.new(encoding)
            codecs.StreamDecoder = StreamDecoderClass

            import micropip
            await micropip.install('pyodide-http')
            import pyodide_http
            pyodide_http.patch_all()
            from pyodide.http import pyfetch
            urllib.request.fetch = pyfetch
        `);

        return pyodide;
    })();

    return initializePromise;
}

messageHandler.register(MessageTypes.LOAD, async () => {
    await initializePyodide();
    safePostMessage(MessageTypes.LOADED);
});

messageHandler.register(MessageTypes.LOAD_PACKAGE, async ({ args }) => {
    if (!pyodide) await initializePyodide();
    safePostMessage(MessageTypes.PACKAGE_LOADED, { result: true });
});

messageHandler.register(MessageTypes.RUN_PYTHON, async ({ args }) => {
    if (!pyodide) await initializePyodide();
    const result = await pyodide.runPythonAsync(...args);
    safePostMessage(MessageTypes.PYTHON_READY, { result });
});

messageHandler.register(MessageTypes.INPUT_RESPONSE, async ({ id, value }) => {
    if (inputResolvers.has(id)) {
        const resolver = inputResolvers.get(id);
        resolver(value);
        inputResolvers.delete(id);
    }
});

self.onmessage = async (event) => {
    try {
        await messageHandler.handle(event.data);
    } catch (error) {
        console.error('Worker error:', error);
        safePostMessage(MessageTypes.ERROR, {
            error: error.toString(),
            stack: error.stack
        });
    }
};