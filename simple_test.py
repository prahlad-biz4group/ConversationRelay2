"""
Simple WebSocket Test - Quick test for the chatbot

Usage:
    python simple_test.py "Your message here"
    
Example:
    python simple_test.py "Hello, how are you?"
"""

import asyncio
import json
import sys
import websockets


async def send_message(message: str):
    """Send a single message and get response"""
    
    uri = "ws://localhost:3000/chat/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"📤 Sending: {message}")
            
            # Send the message as a prompt event
            prompt_event = {
                "type": "prompt",
                "voicePrompt": message,
                "last": True
            }
            await websocket.send(json.dumps(prompt_event))
            
            print(f"📥 Response: ", end="", flush=True)
            
            # Receive response
            full_response = ""
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)
                
                if data["type"] == "text":
                    token = data.get("token", "")
                    if token:
                        full_response += token
                        print(token, end="", flush=True)
                    
                    if data.get("last", False):
                        print("\n")
                        break
            
            return full_response
            
    except ConnectionRefusedError:
        print("\n❌ Connection refused! Make sure BentoML is running:")
        print("   bentoml serve .")
        return None
    except asyncio.TimeoutError:
        print("\n⚠️  Timeout waiting for response")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_test.py \"Your message here\"")
        print("\nExample:")
        print('  python simple_test.py "Hello, how are you?"')
        sys.exit(1)
    
    message = " ".join(sys.argv[1:])
    asyncio.run(send_message(message))


if __name__ == "__main__":
    main()
