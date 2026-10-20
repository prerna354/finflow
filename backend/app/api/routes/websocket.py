import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.redis import CHANNEL, get_async_redis
from app.core.security import decode_access_token

router = APIRouter()


@router.websocket("/ws/transactions")
async def transactions_ws(websocket: WebSocket, token: str = Query(...)):
    """Live payment status updates. Customers see their own payments; admin/analyst see all."""
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=1008)
        return

    user_id = payload.get("sub")
    role = payload.get("role")
    await websocket.accept()

    redis = get_async_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)

    async def forward_events():
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            event = json.loads(message["data"])
            txn = event["transaction"]
            if role in ("admin", "analyst") or user_id in (txn["sender_id"], txn["receiver_id"]):
                await websocket.send_text(message["data"])

    forward_task = asyncio.create_task(forward_events())
    try:
        while True:
            await websocket.receive_text()  # keeps the connection open, raises when the user leaves
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
