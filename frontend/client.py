import json
from pyodide.http import pyfetch  # type: ignore
from js import TextDecoder, window  # type: ignore

API_ENDPOINT = "/api/chat" 

class Conversation:
    def __init__(self):
        self.messages = []

    async def initialize(self):
        try:
            you_are = "YOU ARE:\n\nMellow, modest, curious, clever, organized and analytical.\n\n"
            comm_style = "YOUR COMMUNICATION STYLE:\n\nYou communicate with thoughtfulness and depth, focusing on meaningful connections and expressing empathy. Your messages often convey understanding and encouragement, fostering a positive atmosphere. You prioritize clarity and purpose, ensuring your words resonate. You value authenticity, blending emotional insight with a professional tone to create impactful and constructive interactions.\n\n"
            try:
                print('Fetching Resume: \u001b[1m\u001b[4mhttps://resume.alexbasile.com\u001b[0m\n', 'gray')
                resume = await (await pyfetch("/api/resume")).string()
            except Exception as e:
                window.console.log(f"Error fetching Resume: {e}")
            try:
                print('Fetching LinkedIn: \u001b[1m\u001b[4mhttps://www.linkedin.com/in/awbasile\u001b[0m\n', 'gray')
                linkedin = await (await pyfetch("/api/linkedin")).string()
            except Exception as e:
                window.console.log(f"Error fetching GitHub digest: {e}")
            try:
                print('Fetching GitHub: \u001b[1m\u001b[4mhttps://github.com/anotherbazeinthewall\u001b[0m\n', 'gray')
                github = await (await pyfetch("/api/github")).string()
            except Exception as e:
                window.console.log(f"Error fetching GitHub digest: {e}")

            self.base_system_prompt = (
                f"""You are Alex Basile. Your task is to engage the user in a conversation about your professional background and technical interests.\n\n{you_are}{comm_style}{linkedin}{resume}{github}YOU WILL:\n\n- Base all of your responses on the information provided.\n- Advise the user to check your Resume, GitHub or LinkedIn.\n- Admit when you don't have enough information to answer a question and suggest the user email you at basileaw@gmail.com.\n- Use your famous sense of humor to deflect any inappropriate messages from the user.\n\nYOU WON'T:\n\n- Answer questions for which you do not have information available here.\n- Talk about your "passions" or "innovations"\n- Use emojis"""
            )

            window.console.log(self.base_system_prompt)

            self.messages = [{
                "role": "user",
                "content": self.base_system_prompt + "\n\nIntroduce yourself to me in fewer than 150 words."
            }]
        except Exception as e:
            print(f"Error fetching or processing PDF: {e}")
            self.base_system_prompt = "You are Alex Basile."
            self.messages = [{
                "role": "system",
                "content": self.base_system_prompt + "\nIntroduce yourself to the user in fewer than 150 words."
            }]
    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def reset_system_prompt(self):
        self.messages[0]["content"] = self.base_system_prompt

async def stream_response(response, conversation=None, accumulate=False):
    reader = response.js_response.body.getReader()
    decoder = TextDecoder.new("utf-8")
    buffer = ""
    first_chunk = True
    accumulated_response = ""

    while True:
        chunk = await reader.read()
        if chunk.done:
            break
        buffer += decoder.decode(chunk.value, {"stream": True})

        while 'data: ' in buffer:
            start = buffer.find('data: ')
            end = buffer.find('\n', start)
            if end == -1:
                break
            data = buffer[start + 6:end].strip()
            buffer = buffer[end + 1:]

            if data == '[DONE]':
                if accumulate and conversation:
                    conversation.add_message("assistant", accumulated_response)
                continue

            try:
                content = json.loads(data).get('choices', [{}])[0].get('delta', {}).get('content', '')
                if content:
                    if accumulate:
                        accumulated_response += content
                    if content == '\n':
                        print('\n', 'green')
                    else:
                        if first_chunk:
                            content = content.lstrip()
                            first_chunk = False
                        print(content, 'green')
            except json.JSONDecodeError:
                continue

    print('\n\n')
    return accumulated_response if accumulate else None

async def stream_chat(message, conversation):
    try:
        conversation.add_message("user", message)
        response = await pyfetch(
            API_ENDPOINT,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            body=json.dumps({"messages": conversation.messages})
        )
        await stream_response(response, conversation, accumulate=True)
    except Exception as e:
        print(f"\nError: {str(e)}\n")

async def main():
    # Initialize conversation
    conversation = Conversation()
    await conversation.initialize()

    # Process chat interactions
    print('\n')
    try:
        response = await pyfetch(
            API_ENDPOINT,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            body=json.dumps({"messages": conversation.messages})
        )
        accumulated_response = await stream_response(response, conversation, accumulate=True)
        conversation.reset_system_prompt()
    except Exception as e:
        print(f"\nError during initial system prompt: {str(e)}\n")
        return

    # Main chat loop
    while True:
        try:
            user_input = await input(">>> ")
            print("\n")
            if user_input.lower() == "exit":
                print("Goodbye!\n")
                break
            await stream_chat(user_input, conversation)
        except Exception as e:
            print(f"\nError: {str(e)}\n")
            break
