"""
WebSocket 連接管理模組
處理客戶端的 WebSocket 連接、訊息路由與狀態管理
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 連接管理器"""

    def __init__(self):
        # 存放所有活躍的連接 {client_id: websocket}
        self.active_connections: Dict[str, any] = {}
        # 存放每個連接的狀態 {client_id: state_dict}
        self.connection_states: Dict[str, dict] = {}
        # 訊息佇列 {client_id: asyncio.Queue}
        self.audio_queues: Dict[str, asyncio.Queue] = {}

    async def connect(self, client_id: str, websocket):
        """
        處理新的 WebSocket 連接

        Args:
            client_id: 客戶端唯一識別碼
            websocket: WebSocket 連接物件
        """
        self.active_connections[client_id] = websocket
        self.connection_states[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "status": "connected",
            "conversation_count": 0,
            "last_activity": datetime.now().isoformat()
        }
        self.audio_queues[client_id] = asyncio.Queue()

        logger.info(f"客戶端連接: {client_id}, 總連線數: {len(self.active_connections)}")

    async def disconnect(self, client_id: str):
        """
        處理連接斷開

        Args:
            client_id: 客戶端唯一識別碼
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        if client_id in self.connection_states:
            del self.connection_states[client_id]

        if client_id in self.audio_queues:
            # 清空並刪除音訊佇列
            queue = self.audio_queues.pop(client_id)
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        logger.info(f"客戶端斷開: {client_id}, 剩餘連線數: {len(self.active_connections)}")

    async def send_message(self, client_id: str, message: dict) -> bool:
        """
        發送訊息到指定客戶端

        Args:
            client_id: 客戶端識別碼
            message: 要發送的訊息（dict，會轉為 JSON）

        Returns:
            是否發送成功
        """
        if client_id not in self.active_connections:
            logger.warning(f"嘗試發送到未存在的連接: {client_id}")
            return False

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

            # 更新最後活動時間
            if client_id in self.connection_states:
                self.connection_states[client_id]["last_activity"] = datetime.now().isoformat()

            return True

        except Exception as e:
            logger.error(f"發送訊息失敗: {client_id} - {str(e)}")
            await self.disconnect(client_id)
            return False

    async def send_text(self, client_id: str, text: str, msg_type: str = "text"):
        """
        發送文字訊息

        Args:
            client_id: 客戶端識別碼
            text: 文字內容
            msg_type: 訊息類型
        """
        await self.send_message(client_id, {
            "type": msg_type,
            "content": text,
            "timestamp": datetime.now().isoformat()
        })

    async def send_audio(self, client_id: str, audio_data: bytes):
        """
        發送音訊資料

        Args:
            client_id: 客戶端識別碼
            audio_data: 音訊資料（bytes）
        """
        if client_id not in self.active_connections:
            return

        try:
            import base64
            websocket = self.active_connections[client_id]

            # 將音訊編碼為 base64
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")

            await websocket.send_json({
                "type": "audio",
                "data": audio_b64,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"發送音訊失敗: {client_id} - {str(e)}")

    async def broadcast(self, message: dict, exclude: Optional[Set[str]] = None):
        """
        廣播訊息到所有連接

        Args:
            message: 要發送的訊息
            exclude: 要排除的 client_id 集合
        """
        exclude = exclude or set()
        failed_clients = []

        for client_id in list(self.active_connections.keys()):
            if client_id not in exclude:
                success = await self.send_message(client_id, message)
                if not success:
                    failed_clients.append(client_id)

        # 清理失敗的連接
        for client_id in failed_clients:
            await self.disconnect(client_id)

    def get_state(self, client_id: str) -> Optional[dict]:
        """取得連接狀態"""
        return self.connection_states.get(client_id)

    def get_all_states(self) -> Dict[str, dict]:
        """取得所有連接狀態"""
        return self.connection_states.copy()

    def get_audio_queue(self, client_id: str) -> Optional[asyncio.Queue]:
        """取得音訊佇列"""
        return self.audio_queues.get(client_id)

    async def update_status(self, client_id: str, status: str):
        """更新連接狀態"""
        if client_id in self.connection_states:
            self.connection_states[client_id]["status"] = status

    def get_connection_count(self) -> int:
        """取得連接數量"""
        return len(self.active_connections)


# 建立全域連接管理器實例
connection_manager = ConnectionManager()
