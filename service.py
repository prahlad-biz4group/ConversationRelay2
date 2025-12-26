import asyncio
import os

from fastapi import FastAPI, WebSocket
from starlette.responses import HTMLResponse
from openai import AsyncOpenAI

import bentoml


MAX_NEW_TOKENS = 2048
SYSTEM_PROMPT = """You are a helpful, respectful and honest assistant. You can hear and speak. You are chatting with a user over voice. Your voice and personality should be warm and engaging, with a lively and playful tone, full of charm and energy. The content of your responses should be conversational, nonjudgmental, and friendly.

Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.

If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information."""

OPENAI_MODEL = "gpt-4o"


app = FastAPI()

@app.get('/healthcheck')
def health_check():
    print("Health Check Hitted......")
    return {"success": True, "message": "Working fine."}

@app.post("/start_call")
async def start_call():
    print("POST TwiML")
    service_url = os.environ.get("BENTOCLOUD_DEPLOYMENT_URL")
    assert(service_url)
    if service_url.startswith("http"):
        from urllib.parse import urlparse
        service_url = urlparse(service_url).netloc
    tmpl = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <ConversationRelay url="wss://{service_url}/chat/ws" welcomeGreeting="Hi! I'm Jane from Bento M L. Just chat with me!!"></ConversationRelay>
  </Connect>
</Response>
    """
    return HTMLResponse(content=tmpl.format(service_url=service_url), media_type="application/xml")


@bentoml.service(
    traffic={"timeout": 360},
)
@bentoml.mount_asgi_app(app, path="/chat")
class TwilioChatBot:

    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = AsyncOpenAI(api_key=api_key)


    @app.websocket("/ws")
    async def websocket_endpoint(self, websocket: WebSocket):

        await websocket.accept()
        queue = asyncio.queues.Queue()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # function in charge of getting replies from LLM and updating
        # the message history. This function could be canceled by user
        # interruption.
        async def llm_request(message):
            replies = []
            print(f"[DEBUG] Starting LLM request for message: {message}")

            try:
                print(f"[DEBUG] Calling OpenAI API with model: {OPENAI_MODEL}")
                print(f"[DEBUG] Messages to send: {len(messages + [dict(role='user', content=message)])} messages")
                
                stream = await self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages + [dict(role="user", content=message)],
                    max_tokens=MAX_NEW_TOKENS,
                    stream=True,
                )

                print("[DEBUG] Streaming response from OpenAI...")
                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
                    if chunk.choices[0].delta.content:
                        out = chunk.choices[0].delta.content
                        replies.append(out)
                        print(f"[DEBUG] Received chunk {chunk_count}: {repr(out)}")

                        out_d = {
                            "type": "text",
                            "token": out,
                            "last": False,
                        }
                        await websocket.send_json(out_d)
                
                print(f"[DEBUG] Finished streaming. Total chunks: {chunk_count}, Total reply length: {len(''.join(replies))}")

            except asyncio.CancelledError:
                print("[DEBUG] LLM request cancelled")
                raise
            except Exception as e:
                print(f"[ERROR] Exception in llm_request: {type(e).__name__}: {e}")
                import traceback
                print("[ERROR] Full traceback:")
                traceback.print_exc()

            finally:
                reply = "".join(replies)
                messages.append(dict(role="user", content=message))
                messages.append(dict(role="assistant", content=reply))
                print(f"[DEBUG] Full reply: {reply}")
                print(f"[DEBUG] Message history: {messages}")

                last_d = {
                    "type": "text",
                    "token": "",
                    "last": True,
                }

                await websocket.send_json(last_d)

        async def read_from_socket(websocket: WebSocket):
            async for data in websocket.iter_json():
                queue.put_nowait(data)

        # function in charge of fetching data from queue, launching
        # llm tasks and canceling them when interrupted
        async def get_data_and_process():
            input_buffer = []
            llm_task = None

            async def stop_llm_task():
                nonlocal llm_task
                if llm_task:
                    llm_task.cancel()
                    try:
                        await llm_task
                    except asyncio.CancelledError:
                        pass
                    llm_task = None

            while True:
                data = await queue.get()
                print(f"[DEBUG] Received data: {data}")
                if data["type"] == "prompt":
                    input_buffer.append(data["voicePrompt"])
                    if data["last"]:
                        message = " ".join(input_buffer)
                        input_buffer = []
                        await stop_llm_task()
                        print(f"[DEBUG] Creating LLM task for message: {message}")
                        llm_task = asyncio.create_task(llm_request(message))

                elif data["type"] == "interrupt":
                    input_buffer = []
                    await stop_llm_task()

        await asyncio.gather(read_from_socket(websocket), get_data_and_process())
