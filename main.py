"""
Project AIVT 虛擬主播系統 - 雲端後端主應用
FastAPI + WebSocket 伺服器，整合 DeepSeek、Deepgram 與 GPT-SoVITS
"""

import asyncio
import json
import logging
import base64
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings, verify_settings
from app.connection_manager import connection_manager
from app.deepseek_client import deepseek_client
from app.tts_client import tts_client, simple_tts_client

# 設定日誌
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    # 啟動時
    logger.info("=" * 50)
    logger.info("Project AIVT 虛擬主播系統 後端服務啟動")
    logger.info("=" * 50)

    # 驗證設定
    if not verify_settings():
        logger.warning("設定驗證失敗，請檢查 .env 檔案")

    yield

    # 關閉時
    logger.info("後端服務關閉")


# 建立 FastAPI 應用
app = FastAPI(
    title="Project AIVT API",
    description="虛擬主播系統雲端後端 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API 端點 ====================

@app.get("/")
async def root():
    """根路徑"""
    return {
        "service": "Project AIVT - Virtual Streamer Backend",
        "version": "1.0.0",
        "status": "running",
        "connections": connection_manager.get_connection_count()
    }


@app.get("/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "connections": connection_manager.get_connection_count()
    }


@app.get("/status")
async def get_status():
    """取得系統狀態"""
    return {
        "connections": connection_manager.get_connection_count(),
        "connection_details": connection_manager.get_all_states(),
        "settings": {
            "deepseek_model": settings.deepseek_model,
            "log_level": settings.log_level
        }
    }


# ==================== WebSocket 端點 ====================

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket 連接端點
    處理即時語音對話
    """
    await websocket.accept()

    # 註冊連接
    await connection_manager.connect(client_id, websocket)

    try:
        # 發送歡迎訊息
        await connection_manager.send_text(
            client_id,
            "系統已連接，請開始說話",
            "system"
        )

        # 處理訊息迴圈
        while True:
            try:
                # 接收客戶端訊息
                data = await websocket.receive_json()
                await handle_client_message(client_id, data)

            except json.JSONDecodeError:
                # 嘗試作為文字訊息處理
                try:
                    text = await websocket.receive_text()
                    await handle_client_message(client_id, {"type": "text", "content": text})
                except:
                    pass

            except WebSocketDisconnect:
                break

            except Exception as e:
                logger.error(f"處理訊息錯誤: {str(e)}")
                await connection_manager.send_text(
                    client_id,
                    f"處理訊息時發生錯誤: {str(e)}",
"error"
                )

    except WebSocketDisconnect:
        logger.info(f"客戶端斷開連接: {client_id}")

    except Exception as e:
        logger.error(f"WebSocket 錯誤: {str(e)}")

    finally:
        # 清理連接
        deepseek_client.clear_history()  # 清空對話歷史
        await connection_manager.disconnect(client_id)


async def handle_client_message(client_id: str, data: dict):
    """
    處理來自客戶端的訊息

    Args:
        client_id: 客戶端識別碼
        data: 訊息資料
    """
    msg_type = data.get("type", "text")

    if msg_type == "text":
        # 文字訊息
        content = data.get("content", "")
        if content:
            await handle_text_message(client_id, content)

    elif msg_type == "audio":
        # 音訊訊息（待處理）
        audio_data = data.get("data", "")
        logger.info(f"收到音訊資料: {len(audio_data)} bytes")

    elif msg_type == "interrupt":
        # 中斷訊號
        await handle_interrupt(client_id)

    elif msg_type == "clear_history":
        # 清空對話歷史
        deepseek_client.clear_history()
        await connection_manager.send_text(client_id, "對話歷史已清空", "system")

    else:
        logger.warning(f"未知的訊息類型: {msg_type}")


async def handle_text_message(client_id: str, user_input: str):
    """
    處理文字訊息

    Args:
        client_id: 客戶端識別碼
        user_input: 用戶輸入文字
    """
    logger.info(f"收到文字輸入: {user_input[:50]}...")

    # 發送輸入確認
    await connection_manager.send_text(client_id, f"收到: {user_input}", "echo")

    try:
        # 發送到 DeepSeek 並處理串流回應
        response_text = ""

        async for chunk in deepseek_client.chat(user_input):
            if chunk:
                # 發送文字片段
                await connection_manager.send_text(client_id, chunk, "text_chunk")
                response_text += chunk

        logger.info(f"DeepSeek 回應完成: {len(response_text)} 字元")

        # 發送回應完成訊號
        await connection_manager.send_message(client_id, {
            "type": "response_complete",
            "text": response_text,
            "timestamp": datetime.now().isoformat()
        })

        # 可選：合成語音
        # await synthesize_and_send_audio(client_id, response_text)

    except Exception as e:
        logger.error(f"處理文字訊息錯誤: {str(e)}")
        await connection_manager.send_text(
            client_id,
            f"處理訊息時發生錯誤: {str(e)}",
            "error"
        )


async def handle_interrupt(client_id: str):
    """
    處理中斷訊號
    當用戶打斷 AI 說話時呼叫
    """
    logger.info(f"收到中斷訊號: {client_id}")

    # 發送中斷確認
    await connection_manager.send_text(client_id, "已中斷", "interrupt_ack")

    # TODO: 實現真正的中斷邏輯
    # - 停止當前的 TTS 生成
    # - 清空音訊緩衝區


async def synthesize_and_send_audio(client_id: str, text: str):
    """
    合成語音並發送給客戶端

    Args:
        client_id: 客戶端識別碼
        text: 要合成的文字
    """
    try:
        # 串流獲取音訊
        async for audio_chunk in simple_tts_client.synthesize_stream(text):
            if audio_chunk:
                await connection_manager.send_audio(client_id, audio_chunk)

        logger.info(f"語音合成完成並發送")

    except Exception as e:
        logger.error(f"語音合成錯誤: {str(e)}")


# ==================== REST API 端點 ====================

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """
    REST API 聊天端點（非串流）

    Request Body:
        {
            "message": "用戶訊息",
            "system_prompt": "可選的系統提示"
        }
    """
    user_input = request.get("message", "")
    system_prompt = request.get("system_prompt")

    if not user_input:
        raise HTTPException(status_code=400, detail="訊息不能為空")

    try:
        # 獲取完整回應
        response_text = ""
        async for chunk in deepseek_client.chat(user_input, system_prompt=system_prompt):
            response_text += chunk

        return {
            "success": True,
            "response": response_text,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts")
async def tts_endpoint(request: dict):
    """
    TTS 合成端點

    Request Body:
        {
            "text": "要合成語音的文字"
        }
    """
    text = request.get("text", "")

    if not text:
        raise HTTPException(status_code=400, detail="文字不能為空")

    try:
        # 合成語音
        audio_data = await tts_client.synthesize(text)

        # 編碼為 base64 返回
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        return {
            "success": True,
            "audio": audio_b64,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 主程式 ====================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False
    )
