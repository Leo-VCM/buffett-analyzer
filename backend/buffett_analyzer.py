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
from pydantic import BaseModel, EmailStr

# --- 初始化 ---
app = FastAPI()

# 必須加入 CORS，否則前端 fetch 會失敗
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cache_path = "/tmp/yfinance_stock_cache"
session = requests_cache.CachedSession(cache_path, expire_after=3600, backend='sqlite')

# --- 數據模型 ---
class Subscription(BaseModel):
    email: str

class ComprehensiveResult(BaseModel):
    symbol: str
    companyName: str
    marketPhase: str
    isPositiveMomentum: bool
    finalScore: float
    buffettScore: float  # 新增：為了對齊前端顯示
    currentPrice: float  # 新增：方便前端讀取
    momentum: float     # 新增：1年動能百分比
    recommendation: str
    factors: dict        # 新增：細分評分
    risks: dict          # 新增：風險細分
    details: dict

# --- 核心分析引擎 ---
class BuffettAdvancedAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.stock = yf.Ticker(self.symbol, session=session)

    def analyze(self) -> Optional[dict]:
        try:
            # 頻率保護：若無快取則延遲
            is_cached = session.cache.has_url(f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}")
            if not is_cached:
                time.sleep(random.uniform(0.5, 1.5))

            info = self.stock.info
            hist = self.stock.history(period="1y") 
            if hist.empty or len(hist) < 200: return None

            company_name = info.get('longName', self.symbol)
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
            
            # 1. 趨勢判斷 (MA200)
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            market_phase = "牛市 (Bull)" if current_price > ma200 else "熊市 (Bear)"

            # 2. 動能分析
            # 6個月動能 (判斷是否剔除)
            six_months_ago = hist['Close'].iloc[-126] if len(hist) > 126 else hist['Close'].iloc[0]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
            is_positive_momentum = momentum_6m > 0

            # 1年動能 (前端顯示用)
            one_year_ago = hist['Close'].iloc[0]
            momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100

            # 3. 因子評分 (對齊前端範例的 0-100 分)
            roe = info.get('returnOnEquity', 0)
            norm_roe = (roe * 100) if abs(roe) < 1 else roe
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            margin = info.get('grossMargins', 0)
            
            v_score = 100 if 0 < pe < 15 else (70 if pe < 25 else 30)
            q_score = min(100, norm_roe * 4) if norm_roe > 0 else 0
            m_score = max(0, min(100, momentum_1y + 20))
            g_score = max(0, min(100, (info.get('revenueGrowth', 0) * 100)))

            # 綜合巴菲特分數
            buffett_score = (v_score * 0.4 + q_score * 0.3 + m_score * 0.2 + g_score * 0.1)

            # 4. 最終加權與懲罰
            final_score = buffett_score
            if not is_positive_momentum: final_score *= 0.5
            if market_phase == "熊市 (Bear)": final_score *= 0.8

            # 5. 風險計算
            debt_r = min(100, (info.get('debtToEquity', 0) / 2))
            val_r = min(100, (pe / 40) * 100) if pe > 0 else 50
            vol_r = hist['Close'].pct_change().std() * np.sqrt(252) * 100

            return {
                "symbol": self.symbol,
                "companyName": company_name,
                "currentPrice": round(current_price, 2),
                "marketPhase": market_phase,
                "isPositiveMomentum": is_positive_momentum,
                "momentum": round(momentum_1y, 2),
                "buffettScore": round(buffett_score, 1),
                "finalScore": round(final_score, 1),
                "recommendation": "強力推薦" if final_score > 70 else "觀察" if final_score > 40 else "避開",
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
                "details": {"ma200": round(ma200, 2), "roe": round(norm_roe, 2)}
            }
        except Exception:
            return None

# --- API 端點 ---

@app.post("/api/subscribe")
async def subscribe(sub: Subscription):
    # 儲存到本地檔案 (Render 重新部署後會消失，建議串接 Database)
    with open("/tmp/subscribers.txt", "a") as f:
        f.write(f"{sub.email}\n")
    return {"status": "success"}

@app.get("/api/batch-analyze", response_model=List[ComprehensiveResult])
async def batch_analyze(symbols: str = Query(..., description="以逗號分隔, 如 AAPL,TSLA")):
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    results = []
    for s in symbol_list:
        analysis = BuffettAdvancedAnalyzer(s).analyze()
        if analysis:
            results.append(analysis)
    return results

@app.get("/api/analyze", response_model=ComprehensiveResult)
async def single_analyze(symbol: str = Query(...)):
    res = BuffettAdvancedAnalyzer(symbol).analyze()
    if not res: raise HTTPException(status_code=404)
    return res
