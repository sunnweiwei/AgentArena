import asyncio
import contextlib
import json

import requests
import websockets

BASE_URL = "http://localhost:8000"


def setup_chat():
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "stream-test@example.com"})
    login_resp.raise_for_status()
    user = login_resp.json()
    user_id = user["user_id"]

    chat_resp = requests.post(f"{BASE_URL}/api/chats", params={"user_id": user_id})
    chat_resp.raise_for_status()
    chat = chat_resp.json()
    chat_id = chat["id"]
    return user_id, chat_id


async def run_test():
    user_id, chat_id = setup_chat()
    uri = f"ws://localhost:8000/ws/chat/{chat_id}/{user_id}"
    print(f"Connecting to {uri}")

    async with websockets.connect(uri) as websocket:
        async def receiver():
            async for message in websocket:
                print("Raw:", message, flush=True)
                try:
                    payload = json.loads(message)
                    print("Parsed:", payload, flush=True)
                except json.JSONDecodeError:
                    print("Failed to parse message", flush=True)

        recv_task = asyncio.create_task(receiver())

        payload = {
            "type": "message",
            "content": "Hello! Please describe streaming behavior in detail.",
            "model": "GPT-5-Nano"
        }
        await websocket.send(json.dumps(payload))
        print("Message sent", flush=True)

        try:
            await asyncio.sleep(15)
        finally:
            recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await recv_task


if __name__ == "__main__":
    asyncio.run(run_test())

