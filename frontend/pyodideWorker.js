self.importScripts('https://cdn.jsdelivr.net/pyodide/v0.23.0/full/pyodide.js');
let pyodide = null;
let initializePromise = null;

// Message queue for input responses
let inputResolvers = new Map();
let messageId = 0;

function safePostMessage(type, data) {
    self.postMessage({
        type,
        ...data
    });
}

async function initializePyodide() {
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
        // First, create the pyodide instance with raw output handling
        pyodide = await loadPyodide({
            stdout: (text) => safePostMessage('stdout', { text }), // Remove newline addition
            stderr: (text) => safePostMessage('stderr', { text })  // Remove newline addition
        });

        // Expose objects to Python through self
        self.terminal = {
            write: (text) => safePostMessage('stdout', { text: String(text) })  // Make sure we're passing raw text
        };

        self.input = (prompt) => {
            return new Promise((resolve) => {
                const id = messageId++;
                inputResolvers.set(id, resolve);
                safePostMessage('input', { prompt, id });
            });
        };

        // Basic Python setup
        await pyodide.runPythonAsync(`
            import sys
            import asyncio
            import builtins
            import codecs
            import urllib.request
            from pyodide.ffi import create_proxy
            from js import self

            # Basic print and input functions
            def custom_print(*args, sep=' ', end='\\n', file=None):
                text = sep.join(str(arg) for arg in args)
                # Don't add the end character - let the Python code handle it
                self.terminal.write(text)

            async def custom_input(prompt=''):
                return await self.input(prompt)

            builtins.print = custom_print
            builtins.input = custom_input

            # Set up decoder
            class StreamDecoderClass:
                @staticmethod
                def new(encoding):
                    return self.TextDecoder.new(encoding)

            codecs.StreamDecoder = StreamDecoderClass
        `);

        // Load and set up packages
        await pyodide.loadPackage(['micropip']);

        await pyodide.runPythonAsync(`
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

self.onmessage = async (event) => {
    const { type, args, id, value } = event.data;

    try {
        switch (type) {
            case 'load':
                await initializePyodide();
                safePostMessage('loaded');
                break;

            case 'loadPackage':
                if (!pyodide) await initializePyodide();
                await pyodide.loadPackage(...args);
                safePostMessage('loadPackage', { result: true });
                break;

            case 'runPython':
                if (!pyodide) await initializePyodide();
                const result = await pyodide.runPythonAsync(...args);
                safePostMessage('runPython', { result });
                break;

            case 'inputResponse':
                if (inputResolvers.has(id)) {
                    const resolver = inputResolvers.get(id);
                    resolver(value);
                    inputResolvers.delete(id);
                }
                break;

            default:
                throw new Error(`Unknown message type: ${type}`);
        }
    } catch (error) {
        console.error('Worker error:', error);
        safePostMessage('error', {
            error: error.toString(),
            stack: error.stack
        });
    }
};