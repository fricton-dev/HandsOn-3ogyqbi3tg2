"""LINE 風チャット API (FastAPI + WebSocket)

REST:
  POST /api/auth/signup, /api/auth/login, /api/auth/logout
  GET  /api/me, PATCH /api/me, GET /api/users?q=
  GET  /api/rooms, POST /api/rooms, GET /api/rooms/{id}
  GET  /api/rooms/{id}/messages?before=&limit=
  POST /api/rooms/{id}/messages   (text / sticker)
  POST /api/rooms/{id}/images     (multipart 画像)
  POST /api/rooms/{id}/read       (既読位置の更新)
  DELETE /api/messages/{id}       (送信取消)
  GET  /api/health, /api/info
WebSocket:
  /api/ws?token=...   サーバ → クライアント: message / message_deleted / read / typing / presence / room_created
                      クライアント → サーバ: {"type": "typing", "room_id": N} / {"type": "ping"}
"""
import asyncio
import os
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import auth, db, routes_auth, routes_rooms, seed, services
from .ws import manager

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    seed.seed_if_empty()
    manager.loop = asyncio.get_running_loop()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    db.close_pool()


app = FastAPI(title="Chat API", version="2.0.0", lifespan=lifespan)

_origins_env = os.environ.get("CORS_ORIGINS", "*")
_origins = ["*"] if _origins_env.strip() == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(routes_auth.router)
app.include_router(routes_rooms.router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    try:
        with db.conn() as c:
            row = c.execute("SELECT version()").fetchone()
            db_version, db_ok = row["version"], True
    except Exception as e:  # noqa: BLE001
        db_version, db_ok = f"接続失敗: {e}", False
    return {"api": "FastAPI", "api_hostname": socket.gethostname(), "db_ok": db_ok,
            "db_version": db_version, "online_users": len(manager.online_ids())}


def _typing_targets(room_id: int, user_id: int) -> list[int]:
    with db.conn() as c:
        if not services.is_member(c, room_id, user_id):
            return []
        return [m for m in services.room_member_ids(c, room_id) if m != user_id]


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    user = await run_in_threadpool(auth.user_from_token, token)
    if not user:
        await websocket.close(code=4401)
        return
    await manager.connect(websocket, user["id"])
    await manager.broadcast_all(manager.presence_payload())
    try:
        while True:
            data = await websocket.receive_json()
            kind = data.get("type")
            if kind == "typing":
                room_id = int(data.get("room_id", 0))
                targets = await run_in_threadpool(_typing_targets, room_id, user["id"])
                await manager.send_to_users(targets, {
                    "type": "typing", "room_id": room_id,
                    "user": {"id": user["id"], "display_name": user["display_name"]},
                })
            elif kind == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        manager.disconnect(websocket, user["id"])
        await manager.broadcast_all(manager.presence_payload())
