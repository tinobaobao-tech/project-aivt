"""
DeepSeek API 用戶端模組
處理與 DeepSeek API 的通訊，包括對話生成與串流輸出
"""

import asyncio
import json
from typing import AsyncGenerator, Optional, List, Dict, Any
import httpx
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """DeepSeek API 用戶端類別"""

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model
        self.conversation_history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str):
        """新增訊息到對話歷史"""
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self):
        """清空對話歷史"""
        self.conversation_history = []

    def get_messages(self, system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """取得完整的訊息列表"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 限制歷史長度
        if len(self.conversation_history) > settings.max_conversation_history:
            self.conversation_history = self.conversation_history[-settings.max_conversation_history:]

        messages.extend(self.conversation_history)
        return messages

    async def chat(
        self,
        user_input: str,
        system_prompt: Optional[str] = None,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        發送聊天請求到 DeepSeek API

        Args:
            user_input: 用戶輸入文字
            system_prompt: 系統提示詞（可選）
            stream: 是否使用串流模式

        Yields:
            串流輸出的文字片段
        """
        # 新增用戶訊息到歷史
        self.add_message("user", user_input)

        messages = self.get_messages(system_prompt or settings.default_system_prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 500
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    response.raise_for_status()

                    full_response = ""

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        yield content

                            except json.JSONDecodeError:
                                continue

                    # 新增助手回應到歷史
                    self.add_message("assistant", full_response)
                    logger.info(f"DeepSeek 回應長度: {len(full_response)} 字元")

            except httpx.HTTPStatusError as e:
                logger.error(f"DeepSeek API 錯誤: {e.response.status_code} - {e.response.text}")
                yield f"[錯誤: API 請求失敗，狀態碼 {e.response.status_code}]"

            except Exception as e:
                logger.error(f"DeepSeek API 異常: {str(e)}")
                yield f"[錯誤: {str(e)}]"

    async def chat_simple(self, user_input: str) -> str:
        """
        簡單的非串流聊天請求

        Args:
            user_input: 用戶輸入文字

        Returns:
            完整的回應文字
        """
        response_text = ""

        async for chunk in self.chat(user_input, stream=True):
            response_text += chunk

        return response_text


# 建立全域用戶端實例
deepseek_client = DeepSeekClient()
