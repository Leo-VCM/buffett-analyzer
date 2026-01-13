import os
import logging
import random
import time
from typing import List, Optional

import numpy as np
import pandas as pd
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- 日誌與基礎設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Buffett Stock API")

# 允許跨域請求，讓前端可以順利呼叫
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 強化版快取系統 (關鍵：解決 Too Many Requests) ---
# 在 Render 環境中，只有 /tmp 是可寫入的
session = requests_cache.CachedSession(
    '/tmp/yfinance_cache',
    expire_after=3600, # 資料快取 1 小時
    backend='sqlite'
)

# --- 定義 API 回傳格式 ---
class AnalysisResult(BaseModel):
    symbol: str
    currentPrice: float
    buffettScore: float
    momentum: float
    totalRisk: float
    roe: float
    pe: float
    factors: dict
    risks: dict
    from_cache: bool = False

# --- 你的原始分析邏輯 ---
class BuffettStyleAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        # 使用帶有快取機制的 session
        self.stock = yf.Ticker(self.symbol, session=session)

    def analyze(self):
        try:
            # 檢查是否有快取，若無則強制延遲 1-2 秒，保護 IP 不被封鎖
            is_cached = session.cache.has_url(f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}")
            if not is_cached:
                time.sleep(random.uniform(1.0, 2.0))

            info = self.stock.info
            
            # 取得 1 年歷史數據計算動能與波動
            hist = self.stock.history(period="1y")
            if hist.empty: return None

            # 1. 基礎數據
            price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            
            # ROE 歸一化處理
            raw_roe = info.get('returnOnEquity', 0)
            roe = (raw_roe * 100) if raw_roe and abs(raw_roe) < 1 else (raw_roe or 0)
            
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            debt_to_equity = info.get('debtToEquity', 0)

            # 2. 計算動能 (Momentum)
            close_prices = hist['Close']
            momentum = ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]) * 100
            
            # 3. 計算因子評分 (Factors: 0-100)
            v_score = 100 if 0 < pe < 15 else (70 if pe < 25 else 30)
            q_score = min(100, roe * 4) if roe > 0 else 0
            m_score = max(0, min(100, momentum + 20))
            rev_growth = info.get('revenueGrowth', 0) * 100
            g_score = max(0, min(100, rev_growth))

            # 綜合評分 (Buffett Score)
            buffett_score = (v_score * 0.4 + q_score * 0.3 + m_score * 0.2 + g_score * 0.1)

            # 4. 風險分析 (Risks: 0-100)
            debt_r = min(100, debt_to_equity / 2)
            val_r = min(100, (pe / 40) * 100) if pe > 0 else 50
            vol_r = hist['Close'].pct_change().std() * np.sqrt(252) * 100
            
            total_risk = (debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2)

            return {
                "symbol": self.symbol,
                "currentPrice": round(price, 2),
                "buffettScore": round(buffett_score, 1),
                "momentum": round(momentum, 2),
                "totalRisk": round(total_risk, 1),
                "roe": round(roe, 2),
                "pe": round(pe, 2),
                "factors": {
                    "value": round(v_score, 0),
                    "quality": round(q_score, 0),
                    "momentum": round(m_score, 0),
                    "growth": round(g_score, 0)
                },
                "risks": {
                    "debt": round(debt_r, 1),
                    "valuation": round(val_r, 1),
                    "volatility": round(vol_r, 1)
                },
                "from_cache": is_cached
            }
        except Exception as e:
            logger.error(f"Error analyzing {self.symbol}: {e}")
            return None

# --- API 路由設定 ---

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Buffett Analyzer"}

@app.get("/api/analyze", response_model=AnalysisResult)
async def get_analysis(symbol: str = Query(..., description="股票代號")):
    analyzer = BuffettStyleAnalyzer(symbol)
    result = analyzer.analyze()
    if not result:
        raise HTTPException(status_code=404, detail="無法獲取股票數據")
    return result

# --- 啟動設定 ---
if __name__ == "__main__":
    import uvicorn
    # Render 會傳入 PORT 環境變數
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
