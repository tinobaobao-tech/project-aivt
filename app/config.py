"""
應用程式配置模組
載入並驗證環境變數與應用設定
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """應用程式設定類別"""

    # DeepSeek API 設定
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Deepgram API 設定
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")

    # GPT-SoVITS 設定
    gpt_sovits_model_path: str = os.getenv("GPT_SOVITS_MODEL_PATH", "/models")
    gpt_sovits_port: int = int(os.getenv("GPT_SOVITS_PORT", "5001"))

    # 伺服器設定
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # WebSocket 設定
    ws_max_size: int = int(os.getenv("WS_MAX_SIZE", "10485760"))
    ws_ping_interval: int = int(os.getenv("WS_PING_INTERVAL", "30"))
    ws_ping_timeout: int = int(os.getenv("WS_PING_TIMEOUT", "10"))

    # 對話設定
    max_conversation_history: int = 20
    conversation_window_tokens: int = 4000
    default_system_prompt: str = """你是一位專業的虛擬主播助手，活潑開朗，善于互動。
請用簡潔有趣的語言回應用戶的問題，保持友好的聊天氛圍。
回應長度控制在50-150字以內。"""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 建立全域設定實例
settings = Settings()


def verify_settings() -> bool:
    """驗證必要的設定是否已配置"""
    errors = []

    if not settings.deepseek_api_key or settings.deepseek_api_key == "sk-your-deepseek-api-key-here":
        errors.append("DEEPSEEK_API_KEY 未設定")

    if not settings.deepgram_api_key or settings.deepgram_api_key == "your-deepgram-api-key-here":
        errors.append("DEEPGRAM_API_KEY 未設定")

    if errors:
        print("設定驗證失敗：")
        for error in errors:
            print(f"  - {error}")
        print("\n請複製 .env.example 為 .env 並填入實際的值")
        return False

    print("設定驗證通過")
    return True
