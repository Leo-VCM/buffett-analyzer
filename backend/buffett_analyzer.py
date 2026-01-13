import os
import logging
import random
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# --- 初始化 ---
app = FastAPI()
cache_path = "/tmp/yfinance_stock_cache"
session = requests_cache.CachedSession(cache_path, expire_after=3600, backend='sqlite')

class ComprehensiveResult(BaseModel):
    symbol: str
    companyName: str
    marketPhase: str      # 牛市 (Bull) / 熊市 (Bear)
    isPositiveMomentum: bool # 是否具備正動能
    finalScore: float
    recommendation: str    # 投資建議
    details: dict

class BuffettAdvancedAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.stock = yf.Ticker(self.symbol, session=session)

    def analyze(self) -> Optional[dict]:
        try:
            # 1. 抓取基礎資訊與歷史數據 (需要 1 年以上數據來算 MA200)
            info = self.stock.info
            hist = self.stock.history(period="1y") 
            if hist.empty or len(hist) < 200: return None

            # 2. 公司資訊與全名
            company_name = info.get('longName', self.symbol)

            # --- 3. 牛熊市判斷 (Market Phase) ---
            current_price = hist['Close'].iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            market_phase = "牛市 (Bull)" if current_price > ma200 else "熊市 (Bear)"

            # --- 4. 動能分析 (Momentum Analysis) ---
            # 計算 6 個月的價格變化
            six_months_ago = hist['Close'].iloc[-126] if len(hist) > 126 else hist['Close'].iloc[0]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
            
            # 判斷是否為正動能
            is_positive_momentum = momentum_6m > 0

            # --- 5. 綜合評分邏輯 (剔除負動能) ---
            # 基礎巴菲特評分 (ROE + 毛利)
            roe = info.get('returnOnEquity', 0)
            margin = info.get('grossMargins', 0)
            base_score = (min(100, roe * 400) * 0.5 + min(100, margin * 200) * 0.5)

            # 懲罰機制：如果處於熊市或動能為負，大幅扣分
            final_score = base_score
            if not is_positive_momentum:
                final_score *= 0.5  # 動能為負，分數砍半
            if market_phase == "熊市 (Bear)":
                final_score *= 0.8  # 熊市環境，分數打八折

            # --- 6. 投資建議 ---
            if is_positive_momentum and market_phase == "牛市 (Bull)" and final_score > 70:
                rec = "強力推薦 (Strong Buy)"
            elif is_positive_momentum and final_score > 50:
                rec = "持有/觀察 (Hold)"
            else:
                rec = "避開/賣出 (Avoid)"

            return {
                "symbol": self.symbol,
                "companyName": company_name,
                "marketPhase": market_phase,
                "isPositiveMomentum": is_positive_momentum,
                "finalScore": round(final_score, 1),
                "recommendation": rec,
                "details": {
                    "currentPrice": round(current_price, 2),
                    "ma200": round(ma200, 2),
                    "momentum6m": f"{round(momentum_6m, 2)}%",
                    "roe": round(roe, 4),
                    "margin": round(margin, 4)
                }
            }
        except Exception as e:
            return None

@app.get("/api/analyze", response_model=ComprehensiveResult)
async def get_comprehensive_analysis(symbol: str = Query(...)):
    res = BuffettAdvancedAnalyzer(symbol).analyze()
    if not res: 
        raise HTTPException(status_code=404, detail="分析失敗，請檢查代號或稍後再試")
    return res
