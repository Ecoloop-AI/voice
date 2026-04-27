import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store connected clients by room
rooms = {}  # room_id -> {"python": ws, "web": ws}

async def handle_client(websocket):
    client_type = None
    room_id = None
    
    try:
        # First message must be registration
        reg_msg = await websocket.recv()
        reg = json.loads(reg_msg)
        
        room_id = reg.get("room", "default")
        client_type = reg.get("type")  # "python" or "web"
        
        if room_id not in rooms:
            rooms[room_id] = {}
        
        rooms[room_id][client_type] = websocket
        logger.info(f"[{room_id}] {client_type} client connected. Room: {rooms[room_id].keys()}")
        
        # Notify both sides when both are connected
        await notify_room_status(room_id)
        
        # Relay audio loop
        async for message in websocket:
            room = rooms.get(room_id, {})
            
            if client_type == "python":
                # Python client sent audio → forward to web
                target = room.get("web")
                label = "python→web"
            else:
                # Web client sent audio → forward to python
                target = room.get("python")
                label = "web→python"
            
            if target and target.open:
                await target.send(message)
                logger.info(f"[{room_id}] Relayed {label}: {len(message) if isinstance(message, bytes) else 'text'} bytes")
            else:
                logger.warning(f"[{room_id}] No target for {label}")
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[{room_id}] {client_type} disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if room_id and client_type and room_id in rooms:
            rooms[room_id].pop(client_type, None)
            if not rooms[room_id]:
                del rooms[room_id]
            await notify_room_status(room_id)

async def notify_room_status(room_id):
    room = rooms.get(room_id, {})
    python_connected = "python" in room
    web_connected = "web" in room
    
    status_msg = json.dumps({
        "type": "status",
        "python_connected": python_connected,
        "web_connected": web_connected,
        "both_ready": python_connected and web_connected
    })
    
    for ws in room.values():
        try:
            await ws.send(status_msg)
        except:
            pass

async def health_check(path, request_headers):
    if path == "/health":
        return (200, [("Content-Type", "text/plain")], b"OK")

async def main():
    import os
    port = int(os.environ.get("PORT", 8765))
    logger.info(f"Starting audio relay server on port {port}")
    async with websockets.serve(
        handle_client, 
        "0.0.0.0", 
        port,
        process_request=health_check,
        max_size=10 * 1024 * 1024,  # 10MB max message
        ping_interval=20,
        ping_timeout=10
    ):
        logger.info("Server running...")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
