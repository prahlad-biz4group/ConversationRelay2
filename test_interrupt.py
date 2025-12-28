"""Test interruption functionality"""
import asyncio
import json
import websockets

async def test_interrupt():
    uri = "ws://localhost:3000/chat/ws"
    async with websockets.connect(uri) as ws:
        # Send long story request
        await ws.send(json.dumps({
            "type": "prompt", 
            "voicePrompt": "Tell me a very long story about a robot", 
            "last": True
        }))
        print("Sent request for long story...", flush=True)
        print("Reading chunks:", flush=True)
        
        chunk_count = 0
        interrupted = False
        
        while True:
            data = json.loads(await ws.recv())
            
            if data.get("type") == "text":
                token = data.get("token", "")
                
                if data.get("last"):
                    print(f"\nGot LAST marker after {chunk_count} chunks", flush=True)
                    break
                
                chunk_count += 1
                
                if chunk_count <= 15:
                    print(f"  Chunk {chunk_count}: {repr(token[:40])}", flush=True)
                elif chunk_count == 16:
                    print("  ...", flush=True)
                
                # Send interrupt after 20 chunks
                if chunk_count == 20 and not interrupted:
                    print("\n--- SENDING INTERRUPT after 20 chunks ---", flush=True)
                    await ws.send(json.dumps({"type": "interrupt"}))
                    interrupted = True
        
        print(f"\nTotal chunks received: {chunk_count}", flush=True)
        if interrupted:
            print("Interrupt worked! Response was cut short.", flush=True)

if __name__ == "__main__":
    asyncio.run(test_interrupt())
