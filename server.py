import asyncio
import websockets
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rooms = {}

async def handle_client(websocket):
    client_type = None
    room_id = None
    
    try:
        reg_msg = await websocket.recv()
        reg = json.loads(reg_msg)
        
        room_id = reg.get("room", "default")
        client_type = reg.get("type")
        
        if room_id not in rooms:
            rooms[room_id] = {}
        
        rooms[room_id][client_type] = websocket
        logger.info(f"[{room_id}] {client_type} connected")
        
        await notify_room_status(room_id)
        
        async for message in websocket:
            room = rooms.get(room_id, {})
            if client_type == "python":
                target = room.get("web")
            else:
                target = room.get("python")
            
            if target:
                try:
                    await target.send(message)
                except:
                    pass
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[{room_id}] {client_type} disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if room_id and client_type and room_id in rooms:
            rooms[room_id].pop(client_type, None)
            if not rooms[room_id]:
                del rooms[room_id]

async def notify_room_status(room_id):
    room = rooms.get(room_id, {})
    status_msg = json.dumps({
        "type": "status",
        "python_connected": "python" in room,
        "web_connected": "web" in room,
        "both_ready": "python" in room and "web" in room
    })
    for ws in room.values():
        try:
            await ws.send(status_msg)
        except:
            pass

async def main():
    port = int(os.environ.get("PORT", 8765))
    logger.info(f"Starting server on port {port}")
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        port,
        max_size=10 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=10
    ):
        logger.info("Server running...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
