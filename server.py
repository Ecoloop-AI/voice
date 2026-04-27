import asyncio
import websockets
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# room_id -> set of websockets
rooms = {}

async def handle_client(websocket):
    room_id = None

    try:
        reg_msg = await websocket.recv()
        reg = json.loads(reg_msg)
        room_id = reg.get("room", "default")

        if room_id not in rooms:
            rooms[room_id] = set()

        rooms[room_id].add(websocket)
        count = len(rooms[room_id])
        logger.info(f"[{room_id}] Client joined. Total: {count}")

        # Notify all in room about count
        await notify_room(room_id)

        # Relay loop — send audio to everyone else in room
        async for message in websocket:
            others = rooms.get(room_id, set()) - {websocket}
            for other in others:
                try:
                    await other.send(message)
                except:
                    pass

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[{room_id}] Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if room_id and room_id in rooms:
            rooms[room_id].discard(websocket)
            if not rooms[room_id]:
                del rooms[room_id]
            else:
                await notify_room(room_id)

async def notify_room(room_id):
    room = rooms.get(room_id, set())
    count = len(room)
    status_msg = json.dumps({
        "type": "status",
        "count": count,
        "both_ready": count >= 2
    })
    for ws in room:
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
