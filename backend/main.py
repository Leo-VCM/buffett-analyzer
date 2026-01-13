import logging
import random
import time
import os
from typing import List, Optional

import numpy as np
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- 1. 初始化設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Buffett Stock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 在 Render 上，我們將快取存放在 /tmp 資料夾（Render 的暫存區）
session = requests_cache.CachedSession(
    '/tmp/yfinance_stock_cache',
    expire_after=3600,
    backend='sqlite'
)

# --- 2. 核心分析邏輯 (省略重複的邏輯以節省篇幅，保持與前一份相同) ---
# ... (這裡放之前的 BuffettStyleAnalyzer 類別與 AnalysisResult 模型) ...

# --- 3. API 端點 ---
@app.get("/")
def read_root():
    return {"status": "Buffett Analyzer API is running"}

@app.get("/api/analyze")
def get_stock_analysis(symbol: str = Query(..., description="股票代號")):
    # (保持與之前相同的分析邏輯)
    analyzer = BuffettStyleAnalyzer(symbol)
    result = analyzer.analyze()
    if not result:
        raise HTTPException(status_code=404, detail="Symbol not found or limit reached")
    return result

# --- 4. Render 啟動設定 ---
if __name__ == "__main__":
    # Render 會自動分配 PORT，若沒有則預設 10000
    port = int(os.environ.get("PORT", 10000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
