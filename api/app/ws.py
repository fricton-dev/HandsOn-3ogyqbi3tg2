"""WebSocket 接続の管理と、ユーザー単位のイベント配信。"""
import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[int, set[WebSocket]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)

    def disconnect(self, ws: WebSocket, user_id: int) -> None:
        conns = self.active.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self.active[user_id]

    def online_ids(self) -> list[int]:
        return sorted(self.active.keys())

    async def send_to_users(self, user_ids, payload: dict[str, Any]) -> None:
        for uid in set(user_ids):
            for ws in list(self.active.get(uid, ())):
                try:
                    await ws.send_json(payload)
                except Exception:  # noqa: BLE001
                    self.disconnect(ws, uid)

    async def broadcast_all(self, payload: dict[str, Any]) -> None:
        await self.send_to_users(list(self.active.keys()), payload)

    def send_threadsafe(self, user_ids, payload: dict[str, Any]) -> None:
        """同期エンドポイント (スレッドプール上) から呼ぶための送信。"""
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.send_to_users(list(user_ids), payload), self.loop)

    def presence_payload(self) -> dict[str, Any]:
        return {"type": "presence", "online_user_ids": self.online_ids()}


manager = ConnectionManager()
