import json
import codecs
from urllib.request import fetch
from typing import Tuple, AsyncIterator
        
class Context:
    SOURCES = {
        'Resume': {
            'url': '/api/resume',
            'display_url': 'https://resume.alexbasile.com'
        },
        'LinkedIn': {
            'url': '/api/linkedin',
            'display_url': 'https://www.linkedin.com/in/awbasile'
        },
        'GitHub': {
            'url': '/api/github',
            'display_url': 'https://github.com/anotherbazeinthewall'
        }
    }

    @classmethod
    async def initialize(cls) -> Tuple[str, str]:
        """Returns system prompt and initial message with all context incorporated"""
        # Fetch prompt config first
        try:
            prompt_response = await fetch("/api/prompt_config")
            prompt_config = await prompt_response.json()
            system_prompt_template = prompt_config["system_prompt"]
            initial_message = prompt_config["initial_message"]
        except Exception as e:
            print(f"Error fetching prompt configuration: {str(e)}")
            system_prompt_template = "You are Alex Basile."
            initial_message = "Tell me a joke about technical difficulties."

        # Then fetch context sequentially
        context_values = []
        for name, source in cls.SOURCES.items():
            try:
                print(f'\u001b[90mRetrieving {name}: \u001b[1m\u001b[4m{source["display_url"]}\u001b[0m\n')
                content = await (await fetch(source['url'])).string()
                context_values.append(content)
            except Exception as e:
                print(f"Error fetching {name} context: {str(e)}")
                continue
                
        system_prompt = system_prompt_template.format(resources="\n".join(context_values))
        return system_prompt, initial_message

class StreamProcessor:
    def __init__(self):
        self.decoder = globals()['self'].TextDecoder.new("utf-8")

    @staticmethod
    def new(encoding):
        return globals()['self'].TextDecoder.new(encoding)

    async def process_stream(self, response) -> AsyncIterator[str]:
        reader = response.js_response.body.getReader()
        buffer, first_chunk = "", True
        
        while True:
            if (chunk := await reader.read()).done: break
            buffer += self.decoder.decode(chunk.value, {"stream": True})
            
            while 'data: ' in buffer:
                if (end := buffer.find('\n', start := buffer.find('data: '))) == -1: break
                if (data := buffer[start + 6:end].strip()) == '[DONE]':
                    buffer = buffer[end + 1:]
                    continue
                    
                try:
                    if content := json.loads(data).get('choices', [{}])[0].get('delta', {}).get('content', ''):
                        yield content.lstrip() if first_chunk else content
                        first_chunk = False
                except json.JSONDecodeError:
                    pass
                buffer = buffer[end + 1:]

class ChatInterface:
    codecs.StreamDecoder = StreamProcessor

    def __init__(self):
        self.conversation = Conversation()
        self.stream_processor = StreamProcessor()
    
    async def initialize(self):
        await self.conversation.initialize()
        print('\n')
        try:
            response = await self._make_chat_request()
            await self._handle_stream(response, accumulate=True)
            self.conversation.reset_system_prompt()
        except Exception as e:
            print(f"\nError during initial system prompt: {str(e)}\n")
            return False
        return True
    
    async def _make_chat_request(self):
        return await fetch(
            "/api/chat",
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            body=json.dumps({"messages": self.conversation.messages})
        )
    
    async def _handle_stream(self, response, accumulate=False):
        accumulated = ""
        async for content in self.stream_processor.process_stream(response):
            if accumulate:
                accumulated += content
            self._print_content(content)
        
        self._print_completion()
        if accumulate:
            self.conversation.add_message("assistant", accumulated)
    
    def _print_content(self, content: str):
        print('\n' if content == '\n' else f'\033[92m{content}\033[0m')
            
    def _print_completion(self):
        print('\n\n')
    
    async def handle_user_input(self, user_input: str) -> bool:
        if user_input.lower() == "exit":
            print("Goodbye!\n")
            return False
            
        try:
            self.conversation.add_message("user", user_input)
            response = await self._make_chat_request()
            await self._handle_stream(response, accumulate=True)
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            return False
        return True

class Conversation:
    def __init__(self):
        self.messages = []
        
    async def initialize(self):
        system_prompt, initial_message = await Context.initialize()
        
        self.base_system_prompt = system_prompt
        self.messages = [
            {"role": "system", "content": self.base_system_prompt},
            {"role": "user", "content": initial_message}
        ]

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def reset_system_prompt(self):
        self.messages[0]["content"] = self.base_system_prompt

async def main():
    chat_interface = ChatInterface()
    if not await chat_interface.initialize():
        return
    
    while True:
        try:
            user_input = await input(">>> ")
            print("\n")
            if not await chat_interface.handle_user_input(user_input):
                break
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            break