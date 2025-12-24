import json
import os
import time
import requests
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI()

# --- 步驟 1: 務必先設定 CORSMiddleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, # 建議加上這行
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 步驟 2: 設定常數 ---
CACHE_FILE = "sp500_cache.json"
CACHE_EXPIRE_SECONDS = 86400

# --- 步驟 3: 定義工具函數 ---
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    df = pd.read_html(res.text)[0]
    return df['Symbol'].tolist()

# --- 步驟 4: 定義所有路由 ---
@app.get("/")
def read_root():
    return {
        "status": "Online",
        "project": "Buffett Style S&P 500 Analyzer",
        "api_endpoint": "/api/sp500-analysis",
        "message": "Welcome!"
    }

@app.get("/api/sp500-analysis")
def get_analysis():
    # ... 你的分析邏輯 (保持不變) ...
    if os.path.exists(CACHE_FILE):
        file_time = os.path.getmtime(CACHE_FILE)
        if (time.time() - file_time) < CACHE_EXPIRE_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    
    # (其餘邏輯...)
    # 建議在 try block 加上更詳細的 print 方便看 Render 日誌
    try:
        all_tickers = get_sp500_tickers()
        test_tickers = all_tickers[:50]
        # ...
        # (後面邏輯維持原樣)
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
