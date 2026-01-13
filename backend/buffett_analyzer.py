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

# --- 初始化 ---
app = FastAPI(title="Buffett Analyzer API", version="2.0")

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 快取設定
cache_path = "/tmp/yfinance_stock_cache"
session = requests_cache.CachedSession(cache_path, expire_after=3600, backend='sqlite')

# 日誌設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 數據模型 ---
class Subscription(BaseModel):
    email: str

class ComprehensiveResult(BaseModel):
    symbol: str
    companyName: str
    marketPhase: str
    isPositiveMomentum: bool
    finalScore: float
    buffettScore: float
    currentPrice: float
    momentum: float
    totalRisk: float  # 新增：總風險值（前端需要）
    roe: float        # 新增：直接回傳 ROE（前端卡片需要）
    pe: float         # 新增：直接回傳 P/E（前端卡片需要）
    recommendation: str
    factors: dict
    risks: dict
    details: dict

# --- 核心分析引擎 ---
class BuffettAdvancedAnalyzer:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.stock = yf.Ticker(self.symbol, session=session)

    def analyze(self) -> Optional[dict]:
        try:
            # API 速率保護
            is_cached = session.cache.has_url(
                f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}"
            )
            if not is_cached:
                time.sleep(random.uniform(0.5, 1.5))

            info = self.stock.info
            hist = self.stock.history(period="1y")
            
            # 數據有效性檢查
            if hist.empty or len(hist) < 50:
                logger.warning(f"{self.symbol}: 歷史數據不足")
                return None

            # 基本資訊提取
            company_name = info.get('longName', self.symbol)
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                hist['Close'].iloc[-1]
            )
            
            # 1. 趨勢判斷 (MA200)
            ma200_period = min(200, len(hist))
            ma200 = hist['Close'].rolling(window=ma200_period).mean().iloc[-1]
            market_phase = "牛市 (Bull)" if current_price > ma200 else "熊市 (Bear)"

            # 2. 動能分析
            # 6個月動能（篩選用）
            six_months_idx = min(126, len(hist) - 1)
            six_months_ago = hist['Close'].iloc[-six_months_idx] if six_months_idx > 0 else hist['Close'].iloc[0]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
            is_positive_momentum = momentum_6m > 0

            # 1年動能（展示用）
            one_year_ago = hist['Close'].iloc[0]
            momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100

            # 3. 因子評分 (0-100 分)
            # 價值因子
            roe = info.get('returnOnEquity', 0)
            norm_roe = (roe * 100) if abs(roe) < 1 else roe
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            
            # 修正：避免 PE 過高導致異常
            pe = min(pe, 200) if pe > 0 else 0
            
            v_score = 100 if 0 < pe < 15 else (70 if pe < 25 else 30)
            q_score = min(100, max(0, norm_roe * 4)) if norm_roe > 0 else 0
            m_score = max(0, min(100, momentum_1y + 20))
            
            # 成長因子
            revenue_growth = info.get('revenueGrowth', 0)
            g_score = max(0, min(100, revenue_growth * 100)) if revenue_growth else 50

            # 綜合巴菲特分數
            buffett_score = (
                v_score * 0.4 + 
                q_score * 0.3 + 
                m_score * 0.2 + 
                g_score * 0.1
            )

            # 4. 最終加權與懲罰
            final_score = buffett_score
            if not is_positive_momentum:
                final_score *= 0.5
            if market_phase == "熊市 (Bear)":
                final_score *= 0.8

            # 5. 風險計算
            debt_to_equity = info.get('debtToEquity', 0)
            debt_r = min(100, (debt_to_equity / 2)) if debt_to_equity else 0
            
            val_r = min(100, (pe / 40) * 100) if pe > 0 else 50
            
            # 波動率（年化）
            returns = hist['Close'].pct_change().dropna()
            vol_r = returns.std() * np.sqrt(252) * 100 if len(returns) > 0 else 50
            
            # 總風險（三項平均）
            total_risk = (debt_r + val_r + vol_r) / 3

            # 6. 推薦建議
            if final_score > 70:
                recommendation = "強力推薦"
            elif final_score > 40:
                recommendation = "觀察"
            else:
                recommendation = "避開"

            return {
                "symbol": self.symbol,
                "companyName": company_name,
                "currentPrice": round(float(current_price), 2),
                "marketPhase": market_phase,
                "isPositiveMomentum": is_positive_momentum,
                "momentum": round(float(momentum_1y), 2),
                "buffettScore": round(float(buffett_score), 1),
                "finalScore": round(float(final_score), 1),
                "totalRisk": round(float(total_risk), 1),
                "roe": round(float(norm_roe), 2),
                "pe": round(float(pe), 2),
                "recommendation": recommendation,
                "factors": {
                    "value": int(round(v_score)),
                    "quality": int(round(q_score)),
                    "momentum": int(round(m_score)),
                    "growth": int(round(g_score))
                },
                "risks": {
                    "debt": round(float(debt_r), 1),
                    "valuation": round(float(val_r), 1),
                    "volatility": round(float(vol_r), 1)
                },
                "details": {
                    "ma200": round(float(ma200), 2),
                    "roe": round(float(norm_roe), 2),
                    "pe": round(float(pe), 2),
                    "momentum_6m": round(float(momentum_6m), 2)
                }
            }
            
        except Exception as e:
            logger.error(f"{self.symbol} 分析失敗: {str(e)}")
            return None

# --- API 端點 ---

@app.get("/")
async def root():
    return {
        "service": "Buffett Analyzer API",
        "version": "2.0",
        "endpoints": {
            "batch": "/api/batch-analyze?symbols=AAPL,MSFT",
            "single": "/api/analyze?symbol=AAPL",
            "subscribe": "/api/subscribe (POST)"
        }
    }

@app.post("/api/subscribe")
async def subscribe(sub: Subscription):
    """訂閱服務（建議改用資料庫儲存）"""
    try:
        with open("/tmp/subscribers.txt", "a") as f:
            f.write(f"{sub.email}\n")
        logger.info(f"新訂閱: {sub.email}")
        return {"status": "success", "message": "訂閱成功"}
    except Exception as e:
        logger.error(f"訂閱失敗: {str(e)}")
        raise HTTPException(status_code=500, detail="訂閱失敗")

@app.get("/api/batch-analyze", response_model=List[ComprehensiveResult])
async def batch_analyze(
    symbols: str = Query(
        ..., 
        description="逗號分隔的股票代號，如: AAPL,MSFT,GOOGL",
        example="AAPL,MSFT,TSLA"
    )
):
    """批次分析多支股票"""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    
    if len(symbol_list) > 20:
        raise HTTPException(
            status_code=400, 
            detail="單次最多分析 20 支股票"
        )
    
    results = []
    for symbol in symbol_list:
        logger.info(f"開始分析: {symbol}")
        analysis = BuffettAdvancedAnalyzer(symbol).analyze()
        if analysis:
            results.append(analysis)
        else:
            logger.warning(f"{symbol} 分析失敗或數據不足")
    
    if not results:
        raise HTTPException(
            status_code=404, 
            detail="所有股票分析失敗，請檢查代號是否正確"
        )
    
    # 按 buffettScore 降序排序
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    
    return results

@app.get("/api/analyze", response_model=ComprehensiveResult)
async def single_analyze(
    symbol: str = Query(..., description="股票代號", example="AAPL")
):
    """單一股票分析"""
    symbol = symbol.strip().upper()
    logger.info(f"單一分析: {symbol}")
    
    result = BuffettAdvancedAnalyzer(symbol).analyze()
    
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"{symbol} 分析失敗：可能數據不足或代號錯誤"
        )
    
    return result

# --- 健康檢查端點 ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "cache_path": cache_path,
        "cache_exists": os.path.exists(cache_path)
    }
