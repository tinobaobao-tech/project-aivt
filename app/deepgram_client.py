"""
Deepgram 語音識別用戶端模組
處理即時語音轉文字功能
"""

import asyncio
import json
from typing import AsyncGenerator, Optional
from deepgram import Deepgram
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class DeepgramClient:
    """Deepgram 語音識別用戶端類別"""

    def __init__(self):
        self.api_key = settings.deepgram_api_key
        self.dg_client = Deepgram(self.api_key)
        self.connection: Optional[any] = None
        self.is_recording = False

    async def start_streaming(
        self,
        audio_queue: asyncio.Queue,
        callback: Optional[callable] = None
    ):
        """
        開始串流語音識別

        Args:
            audio_queue: 音訊資料佇列
            callback: 回調函數，用於處理識別結果
        """
        self.is_recording = True

        try:
            # 建立 WebSocket 連接
            self.connection = await self.dg_client.transcription.live(
                {
                    "model": "nova-2",
                    "language": "zh-TW",  # 繁體中文
                    "interim_results": True,
                    "punctuation": True,
                    " diarize": False,
                    "encoding": "mulaw",
                    "sample_rate": 16000,
                }
            )

            # 設定事件處理
            self.connection.on("transcriptReceived", callback or self._default_callback)

            # 開始接收音訊
            asyncio.create_task(self._receive_audio(audio_queue))

            logger.info("Deepgram 串流識別已啟動")

        except Exception as e:
            logger.error(f"啟動 Deepgram 串流失敗: {str(e)}")
            self.is_recording = False
            raise

    async def _receive_audio(self, audio_queue: asyncio.Queue):
        """從佇列接收音訊並發送到 Deepgram"""
        try:
            while self.is_recording:
                try:
                    # 嘗試從佇列獲取音訊，設定逾時
                    audio_data = await asyncio.wait_for(audio_queue.get(), timeout=1.0)

                    if audio_data is None:  # 結束訊號
                        break

                    if self.connection:
                        self.connection.send(audio_data)

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"音訊處理錯誤: {str(e)}")
                    break

        finally:
            if self.connection:
                self.connection.finish()
            self.is_recording = False
            logger.info("Deepgram 串流識別已停止")

    def _default_callback(self, response: dict):
        """預設的回調函數"""
        try:
            if "channel" in response and "alternatives" in response["channel"]:
                transcript = response["channel"]["alternatives"][0].get("transcript", "")
                is_final = response.get("is_final", False)

                if transcript:
                    logger.info(f"Deepgram 識別結果: {'[最終] ' if is_final else '[暫時] '}{transcript}")

        except Exception as e:
            logger.error(f"Deepgram 回調處理錯誤: {str(e)}")

    async def stop_streaming(self):
        """停止串流識別"""
        self.is_recording = False
        if self.connection:
            self.connection.finish()
            self.connection = None
        logger.info("Deepgram 串流已停止")


# 建立全域用戶端實例
deepgram_client = DeepgramClient()
