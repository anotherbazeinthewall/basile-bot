import json
import codecs
from urllib.request import fetch
from typing import Optional, Dict, Tuple, AsyncIterator

class Config:
    RESOURCES = {
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
    
    PROMPT_TEMPLATES = {
        'you_are': "YOU ARE:\n\nMellow, modest, curious, clever, organized and analytical.\n\n",
        'comm_style': "YOUR COMMUNICATION STYLE:\n\nYou use active voice and do not editorialize. You communicate with thoughtfulness, depth and humor. Your messages often convey understanding and encouragement, fostering a positive atmosphere. You prioritize clarity and purpose, ensuring your words resonate. You value authenticity, blending emotional insight with a professional tone to create impactful and constructive interactions.\n\n",
        'initial_message': "Introduce yourself to me in fewer than 150 words. Offer to chat about any aspect of your professional experience that I'd like to know more about."
    }
    
    @staticmethod
    def create_system_prompt(resources: Dict[str, str]) -> str:
        return f"""You are Alex Basile. Your task is to engage the user in a conversation about your professional background and technical interests.\n\n{Config.PROMPT_TEMPLATES['you_are']}{Config.PROMPT_TEMPLATES['comm_style']}{"".join(resources.values())}YOU WILL:\n\n- Base all of your responses on the information provided.\n- Admit when you don't have enough information to answer a question and suggest the user email you at basileaw@gmail.com.\n- Advise the user to check the links at the top of the page for your Resume, GitHub or LinkedIn.\n- Use your famous sense of humor to deflect any inappropriate messages from the user.\n\nYOU WON'T:\n\n- Answer questions for which you do not have information available here.\n- Use pretentious language like "passionate", "innovative", "complex" or "cutting edge"\n- Use emojis"""

class ResourceFetcher:
    @staticmethod
    async def fetch_resource(resource_name: str) -> Tuple[Optional[str], Optional[str]]:
        if resource_name not in Config.RESOURCES:
            return None, f"Unknown resource: {resource_name}"

        resource = Config.RESOURCES[resource_name]
        try:
            print(f'\u001b[90mFetching {resource_name}: \u001b[1m\u001b[4m{resource["display_url"]}\u001b[0m\n')
            return (await (await fetch(resource['url'])).string()), None
        except Exception as e:
            error_msg = f"Error fetching {resource_name}: {str(e)}"
            return None, error_msg

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

class ChatManager:
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
        resources = {}
        for resource_name in Config.RESOURCES.keys():
            content, _ = await ResourceFetcher.fetch_resource(resource_name)
            if content:
                resources[resource_name] = content

        self.base_system_prompt = (Config.create_system_prompt(resources) if resources 
                                 else "You are Alex Basile.")
        
        self.messages = [
            {"role": "system", "content": self.base_system_prompt},
            {"role": "user", "content": Config.PROMPT_TEMPLATES['initial_message']}
        ]

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def reset_system_prompt(self):
        self.messages[0]["content"] = self.base_system_prompt

async def main():
    codecs.StreamDecoder = StreamProcessor
    chat_manager = ChatManager()
    if not await chat_manager.initialize():
        return
        
    while True:
        try:
            user_input = await input(">>> ")
            print("\n")
            if not await chat_manager.handle_user_input(user_input):
                break
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            break