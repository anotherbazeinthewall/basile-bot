const MessageTypes = {
    STDOUT: 'stdout', STDERR: 'stderr', INPUT: 'input', INPUT_RESPONSE: 'inputResponse',
    LOAD: 'load', LOADED: 'loaded', LOAD_PACKAGE: 'loadPackage', PACKAGE_LOADED: 'packageLoaded',
    RUN_PYTHON: 'runPython', PYTHON_READY: 'pythonReady', ERROR: 'error'
};

class MessageHandler {
    constructor() { this.handlers = new Map(); }

    register(messageType, handler) {
        if (!Object.values(MessageTypes).includes(messageType)) {
            console.warn(`Unknown message type: ${messageType}`);
        }
        this.handlers.set(messageType, handler);
    }

    async handle(message) {
        if (!message?.type || !Object.values(MessageTypes).includes(message.type)) {
            console.warn('Invalid message:', message);
            return;
        }
        const handler = this.handlers.get(message.type);
        handler ? await handler(message) : console.warn(`No handler for: ${message.type}`);
    }
}

// Handle both browser and worker contexts
if (typeof window !== 'undefined') {
    window.MessageTypes = MessageTypes;
    window.MessageHandler = MessageHandler;
} else {
    self.MessageTypes = MessageTypes;
    self.MessageHandler = MessageHandler;
}