"""
GPT-SoVITS 語音合成用戶端模組
處理文字轉語音功能，支援串流輸出
"""

import asyncio
import json
import base64
import numpy as np
from typing import AsyncGenerator, Optional
import httpx
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class TTSClient:
    """GPT-SoVITS 語音合成用戶端類別"""

    def __init__(self):
        self.base_url = f"http://localhost:{settings.gpt_sovits_port}"
        self.model_loaded = False

    async def synthesize_stream(
        self,
        text: str,
        speed: float = 1.0,
        language: str = "zh"
    ) -> AsyncGenerator[bytes, None]:
        """
        串流合成語音

        Args:
            text: 要合成的文字
            speed: 語速倍率
            language: 語言代碼

        Yields:
            音訊資料（bytes）
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 發送合成請求
                response = await client.post(
                    f"{self.base_url}/tts",
                    json={
                        "text": text,
                        "speed": speed,
                        "language": language,
                        "stream": True
                    },
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                # 串流接收音訊資料
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

                logger.info(f"TTS 合成完成: {len(text)} 字元")

        except httpx.HTTPStatusError as e:
            logger.error(f"TTS API 錯誤: {e.response.status_code}")
            yield self._create_error_audio(f"語音合成失敗，狀態碼 {e.response.status_code}")

        except Exception as e:
            logger.error(f"TTS 異常: {str(e)}")
            yield self._create_error_audio(f"語音合成錯誤: {str(e)}")

    async def synthesize(self, text: str) -> bytes:
        """
        非串流合成（完整音訊）

        Args:
            text: 要合成的文字

        Returns:
            完整的音訊資料
        """
        audio_chunks = []

        async for chunk in self.synthesize_stream(text):
            audio_chunks.append(chunk)

        return b"".join(audio_chunks)

    def _create_error_audio(self, message: str) -> bytes:
        """建立錯誤提示音訊（靜音）"""
        # 返回空的音訊資料
        return b""

    async def check_health(self) -> bool:
        """檢查 TTS 服務是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


class SimpleTTSClient:
    """簡化的 TTS 用戶端，使用系統預設 TTS"""

    async def synthesize_stream(
        self,
        text: str,
        speed: float = 1.0,
        language: str = "zh"
    ) -> AsyncGenerator[bytes, None]:
        """
        模擬串流合成（實際使用本地代處理）

        Args:
            text: 要合成的文字
            speed: 語速倍率
            language: 語言代碼

        Yields:
            模擬的音訊資料
        """
        # 記錄要合成的文字
        logger.info(f"[模擬 TTS] 文字: {text[:50]}...")

        # 這裡返回一個簡單的提示音
        # 實際部署時應替換為真正的 GPT-SoVITS 服務
        yield b"SILENCE"


# 建立全域用戶端實例
tts_client = TTSClient()
simple_tts_client = SimpleTTSClient()
