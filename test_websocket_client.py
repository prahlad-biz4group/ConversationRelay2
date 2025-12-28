"""
WebSocket Test Client for Twilio ConversationRelay Simulation

This script simulates Twilio's ConversationRelay WebSocket events
to test the voice chatbot locally without needing an actual phone call.

Usage:
    python test_websocket_client.py
"""

import asyncio
import json
import websockets


async def test_conversation():
    """Simulate a conversation with the chatbot via WebSocket"""
    
    # Connect to the WebSocket endpoint
    uri = "ws://localhost:3000/chat/ws"
    
    print(f"🔌 Connecting to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        print("✅ Connected to WebSocket!")
        print("=" * 60)
        
        # Simulate user messages (like Twilio would send)
        test_messages = [
            "Hello, how are you?",
            "What's the weather like today?",
            "Tell me a joke",
        ]
        
        for i, user_message in enumerate(test_messages, 1):
            print(f"\n📤 User Message {i}: {user_message}")
            
            # Split message into chunks (simulating Twilio's streaming)
            words = user_message.split()
            
            # Send message in chunks (like Twilio does)
            for j, word in enumerate(words):
                prompt_event = {
                    "type": "prompt",
                    "voicePrompt": word,
                    "last": (j == len(words) - 1)
                }
                await websocket.send(json.dumps(prompt_event))
                print(f"  → Sent chunk: {word} (last={prompt_event['last']})")
                await asyncio.sleep(0.1)  # Small delay between words
            
            print(f"\n📥 AI Response:")
            
            # Receive and display the AI's response
            response_text = ""
            while True:
                try:
                    response = await asyncio.wait_for(
                        websocket.recv(), 
                        timeout=30.0
                    )
                    data = json.loads(response)
                    
                    if data["type"] == "text":
                        token = data.get("token", "")
                        if token:
                            response_text += token
                            print(token, end="", flush=True)
                        
                        if data.get("last", False):
                            print("\n")
                            break
                            
                except asyncio.TimeoutError:
                    print("\n⚠️  Timeout waiting for response")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    break
            
            # Wait a bit before next message
            if i < len(test_messages):
                print("\n" + "-" * 60)
                await asyncio.sleep(1)
        
        print("\n" + "=" * 60)
        print("✅ Test completed!")


async def test_interruption():
    """Test user interruption during AI response"""
    
    uri = "ws://localhost:3000/chat/ws"
    
    print(f"\n🔌 Testing interruption at {uri}...")
    
    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")
        
        # Send a message that will generate a long response
        prompt_event = {
            "type": "prompt",
            "voicePrompt": "Tell me a very long story about a robot",
            "last": True
        }
        await websocket.send(json.dumps(prompt_event))
        print("📤 Sent: Tell me a very long story about a robot")
        print("📥 Receiving chunks...")
        
        chunk_count = 0
        interrupted = False
        
        while True:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                if data["type"] == "text":
                    token = data.get("token", "")
                    
                    # Check for last marker first
                    if data.get("last", False):
                        print(f"\n[OK] Got LAST marker after {chunk_count} total chunks", flush=True)
                        if interrupted:
                            print("   Interrupt worked! Response was cut short.", flush=True)
                        break
                    
                    chunk_count += 1
                    
                    # Show first 10 chunks
                    if chunk_count <= 10:
                        print(f"  Chunk {chunk_count}: {repr(token[:30])}", flush=True)
                    elif chunk_count == 11:
                        print("  ...", flush=True)
                    
                    # Send interrupt after 20 chunks
                    if chunk_count == 20 and not interrupted:
                        print("\n[!] --- SENDING INTERRUPT after 20 chunks ---", flush=True)
                        interrupt_event = {"type": "interrupt"}
                        await websocket.send(json.dumps(interrupt_event))
                        interrupted = True
                        
            except asyncio.TimeoutError:
                print("\n⚠️  Timeout waiting for response")
                break
        
        print("✅ Interruption test completed!")


async def main():
    """Run all tests"""
    print("🤖 Twilio WebSocket Test Client")
    print("=" * 60)
    print("Make sure your BentoML service is running on localhost:3000")
    print("=" * 60)
    
    try:
        # Test normal conversation
        await test_conversation()
        
        # Test interruption
        print("\n" + "=" * 60)
        print("🔄 Testing Interruption Feature")
        print("=" * 60)
        await test_interruption()
        
    except ConnectionRefusedError:
        print("\n❌ Connection refused!")
        print("Make sure BentoML service is running:")
        print("  bentoml serve .")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
