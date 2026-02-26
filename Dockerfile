# Project AIVT 後端服務 Docker 映像
FROM python:3.10-slim

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 建立工作目錄
WORKDIR /app

# 複製依賴檔案
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式碼
COPY . .

# 建立 logs 目錄
RUN mkdir -p logs

# 暴露連接埠
EXPOSE 8000

# 啟動命令
CMD ["python", "main.py"]
