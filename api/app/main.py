"""LINE 風チャット API (FastAPI + WebSocket)

ストレージはローカル (PostgreSQL) と共有 (DynamoDB) を設定画面で切り替えられる。
WebSocket による即時配信は同じ API に接続しているブラウザ同士で動き、
共有モードでは他の EC2 からの書き込みを画面側のポーリングで拾う。

REST:
  POST /api/auth/signup, /api/auth/login, /api/auth/logout
  GET  /api/me, PATCH /api/me, GET /api/users?q=
  GET  /api/rooms, POST /api/rooms, GET /api/rooms/{id}
  GET  /api/rooms/{id}/messages?before=&after=&limit=
  POST /api/rooms/{id}/messages   (text / sticker)
  POST /api/rooms/{id}/images     (multipart 画像)
  POST /api/rooms/{id}/read       (既読位置の更新)
  DELETE /api/rooms/{id}/messages/{mid}  (送信取消)
  GET  /api/settings/public, GET/PUT /api/settings, POST /api/settings/test
  GET  /api/health, /api/info
WebSocket:
  /api/ws?token=...   サーバ → クライアント: message / message_deleted / read / typing / presence / room_created
                      クライアント → サーバ: {"type": "typing", "room_id": N} / {"type": "ping"}
"""
import asyncio
import os
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import auth, db, images, routes_auth, routes_rooms, routes_settings, settings
from .ws import manager

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    settings.ensure_table()
    from .storage_postgres import PostgresStorage
    PostgresStorage().seed_demo()          # ローカル DB にだけデモデータを入れる
    manager.loop = asyncio.get_running_loop()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield
    db.close_pool()


app = FastAPI(title="Chat API", version="3.0.0", lifespan=lifespan)

_origins_env = os.environ.get("CORS_ORIGINS", "*")
_origins = ["*"] if _origins_env.strip() == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

app.include_router(routes_auth.router)
app.include_router(routes_rooms.router)
app.include_router(routes_settings.router)


@app.get("/uploads/{name}")
def uploaded_image(name: str):
    """送信画像。この EC2 に保存されていればそれを返し、無ければ S3 の署名付き URL へ転送する。"""
    path = images.local_path(name)
    if path:
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
    url = images.presigned_url(name)
    if url:
        return RedirectResponse(url, status_code=302)
    raise HTTPException(404, "画像が見つかりません")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
def info():
    out = {"api": "FastAPI", "api_hostname": socket.gethostname(), "online_users": len(manager.online_ids())}
    try:
        with db.conn() as c:
            out["db_version"] = c.execute("SELECT version()").fetchone()["version"]
            out["db_ok"] = True
    except Exception as e:  # noqa: BLE001
        out["db_version"], out["db_ok"] = f"接続失敗: {e}", False
    try:
        out["storage"] = settings.active().info()
    except Exception as e:  # noqa: BLE001
        out["storage"] = {"error": str(e)}
    out["images"] = images.info()
    return out


def _typing_targets(room_id: str, user_id) -> list:
    st = settings.active()
    if not st.is_member(room_id, user_id):
        return []
    return [m for m in st.room_member_ids(room_id) if m != user_id]


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
                room_id = str(data.get("room_id", ""))
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
