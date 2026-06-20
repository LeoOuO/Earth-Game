#!/bin/bash
# 最終大戰 WWW 啟動腳本
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "建立虛擬環境..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

PORT="${1:-5001}"
echo "啟動最終大戰伺服器（port $PORT）..."
echo "請在瀏覽器開啟：http://localhost:$PORT"
PORT="$PORT" python app.py
