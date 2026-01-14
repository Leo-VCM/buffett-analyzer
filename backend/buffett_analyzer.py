"""
Buffett Analyzer API - 改進版本
修復數據下載問題，增強錯誤處理
"""
import os
import logging
import random
import time
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==================== 初始化 ====================

app = FastAPI(
    title="Buffett Analyzer API", 
    version="2.1",
    description="巴菲特量化即時分析系統 - 改進版",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 速率限制器 ====================

class RateLimiter:
    """智能速率限制器"""
    
    def __init__(self):
        self.requests = []
        self.max_requests_per_minute = 8  # 降低請求頻率
        self.min_delay_between_requests = 1.5  # 增加延遲
        
    def can_make_request(self) -> bool:
        now = datetime.now()
        self.requests = [req for req in self.requests if now - req < timedelta(minutes=1)]
        return len(self.requests) < self.max_requests_per_minute
    
    def record_request(self):
        self.requests.append(datetime.now())
    
    async def wait_if_needed(self):
        wait_count = 0
        while not self.can_make_request():
            wait_count += 1
            if wait_count == 1:
                logger.warning("⚠️ 達到速率限制，等待中...")
            await asyncio.sleep(10)
        
        await asyncio.sleep(self.min_delay_between_requests)

rate_limiter = RateLimiter()

# ==================== 數據模型 ====================

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
    totalRisk: float
    roe: float
    pe: float
    recommendation: str
    factors: dict
    risks: dict
    details: dict

# ==================== 改進的分析引擎 ====================

class BuffettAdvancedAnalyzer:
    """改進的巴菲特量化分析引擎"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.max_retries = 3
        self.retry_delay = 2

    async def _fetch_with_retry(self, fetch_func, description: str):
        """帶重試的數據獲取"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔄 [{self.symbol}] {description} (嘗試 {attempt + 1}/{self.max_retries})")
                result = fetch_func()
                logger.info(f"✅ [{self.symbol}] {description} 成功")
                return result
            except Exception as e:
                logger.warning(f"⚠️ [{self.symbol}] {description} 失敗 (嘗試 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.info(f"⏳ 等待 {wait_time} 秒後重試...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ [{self.symbol}] {description} 最終失敗")
                    return None
        return None

    async def analyze(self) -> Optional[dict]:
        """改進的非同步分析"""
        try:
            # 速率限制
            await rate_limiter.wait_if_needed()
            rate_limiter.record_request()
            
            # 創建 Ticker 實例
            logger.info(f"🎯 開始分析 {self.symbol}")
            stock = yf.Ticker(self.symbol)
            
            # 1. 獲取基本資料（帶重試）
            info = await self._fetch_with_retry(
                lambda: stock.info,
                "獲取基本資料"
            )
            
            if not info or len(info) < 5:
                logger.error(f"❌ {self.symbol}: 基本資料無效或不完整")
                return None
            
            # 2. 獲取歷史數據（帶重試）
            hist = await self._fetch_with_retry(
                lambda: stock.history(period="1y", interval="1d"),
                "獲取歷史數據"
            )
            
            if hist is None or hist.empty:
                logger.error(f"❌ {self.symbol}: 無法獲取歷史數據")
                return None
            
            if len(hist) < 50:
                logger.warning(f"⚠️ {self.symbol}: 歷史數據不足 ({len(hist)} 天)")
                return None
            
            logger.info(f"📊 [{self.symbol}] 獲得 {len(hist)} 天數據")
            
            # 3. 提取基本資訊
            company_name = (
                info.get('longName') or 
                info.get('shortName') or 
                info.get('symbol') or 
                self.symbol
            )
            
            # 獲取當前價格（多種方式嘗試）
            current_price = (
                info.get('currentPrice') or
                info.get('regularMarketPrice') or
                info.get('previousClose') or
                hist['Close'].iloc[-1]
            )
            
            if not current_price or current_price <= 0:
                logger.error(f"❌ {self.symbol}: 無效價格 {current_price}")
                return None
            
            current_price = float(current_price)
            logger.info(f"💰 [{self.symbol}] 當前價格: ${current_price:.2f}")
            
            # 4. 市場階段判斷
            ma_period = min(200, len(hist))
            ma200 = hist['Close'].rolling(window=ma_period).mean().iloc[-1]
            market_phase = "牛市 (Bull)" if current_price > ma200 else "熊市 (Bear)"
            
            # 5. 動能計算
            six_months_idx = min(126, len(hist) - 1)
            six_months_ago = hist['Close'].iloc[-six_months_idx] if six_months_idx > 0 else hist['Close'].iloc[0]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100 if six_months_ago > 0 else 0
            
            one_year_ago = hist['Close'].iloc[0]
            momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100 if one_year_ago > 0 else 0
            
            is_positive_momentum = momentum_1y > 0
            
            # 6. 財務指標提取（使用安全的預設值）
            roe = info.get('returnOnEquity', 0) or 0
            norm_roe = (roe * 100) if abs(roe) < 1 else roe
            norm_roe = max(-100, min(200, norm_roe))  # 限制在合理範圍
            
            pe = (
                info.get('forwardPE') or 
                info.get('trailingPE') or 
                info.get('priceToBook', 0) * 15 or  # 用 P/B 估算
                25
            )
            pe = max(1, min(200, pe))  # 限制範圍
            
            debt_to_equity = info.get('debtToEquity', 50) or 50
            debt_to_equity = max(0, min(500, debt_to_equity))
            
            revenue_growth = info.get('revenueGrowth', 0) or 0
            
            # 7. 因子評分
            # 價值因子
            if 0 < pe < 15:
                v_score = 100
            elif pe < 25:
                v_score = 70
            elif pe < 40:
                v_score = 40
            else:
                v_score = 20
            
            # 質量因子
            q_score = min(100, max(0, norm_roe * 3)) if norm_roe > 0 else 30
            
            # 動能因子
            m_score = max(0, min(100, (momentum_1y + 50) * 1.5))
            
            # 成長因子
            g_score = max(0, min(100, (revenue_growth * 100 + 50)))
            
            # 8. 巴菲特綜合評分
            buffett_score = (
                v_score * 0.35 +
                q_score * 0.35 +
                m_score * 0.20 +
                g_score * 0.10
            )
            
            # 9. 最終評分（考慮市場階段）
            final_score = buffett_score
            
            if not is_positive_momentum:
                final_score *= 0.6
            
            if market_phase == "熊市 (Bear)":
                final_score *= 0.85
            
            # 10. 風險評估
            debt_r = min(100, (debt_to_equity / 3))
            val_r = min(100, (pe / 40) * 100)
            
            returns = hist['Close'].pct_change().dropna()
            if len(returns) > 20:
                vol_r = min(100, returns.std() * np.sqrt(252) * 100)
            else:
                vol_r = 50
            
            total_risk = (debt_r + val_r + vol_r) / 3
            
            # 11. 投資建議
            if final_score > 70 and total_risk < 40:
                recommendation = "強力推薦"
            elif final_score > 50 and total_risk < 60:
                recommendation = "可考慮"
            elif final_score > 35:
                recommendation = "觀察"
            else:
                recommendation = "避開"
            
            logger.info(f"✅ [{self.symbol}] 評分: {buffett_score:.1f}, 建議: {recommendation}")
            
            # 12. 返回結果
            return {
                "symbol": self.symbol,
                "companyName": company_name,
                "currentPrice": round(current_price, 2),
                "marketPhase": market_phase,
                "isPositiveMomentum": is_positive_momentum,
                "momentum": round(momentum_1y, 2),
                "buffettScore": round(buffett_score, 1),
                "finalScore": round(final_score, 1),
                "totalRisk": round(total_risk, 1),
                "roe": round(norm_roe, 2),
                "pe": round(pe, 2),
                "recommendation": recommendation,
                "factors": {
                    "value": int(round(v_score)),
                    "quality": int(round(q_score)),
                    "momentum": int(round(m_score)),
                    "growth": int(round(g_score))
                },
                "risks": {
                    "debt": round(debt_r, 1),
                    "valuation": round(val_r, 1),
                    "volatility": round(vol_r, 1)
                },
                "details": {
                    "ma200": round(ma200, 2),
                    "roe": round(norm_roe, 2),
                    "pe": round(pe, 2),
                    "momentum_6m": round(momentum_6m, 2),
                    "data_points": len(hist)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.symbol}] 分析異常: {str(e)}", exc_info=True)
            return None

# ==================== API 端點 ====================

@app.get("/")
async def root():
    return {
        "service": "Buffett Analyzer API",
        "version": "2.1",
        "status": "operational",
        "improvements": [
            "增強錯誤處理",
            "自動重試機制",
            "更穩定的數據獲取",
            "更安全的預設值處理"
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "analyze": "/api/analyze?symbol=AAPL",
            "batch": "/api/batch-analyze?symbols=AAPL,MSFT,GOOGL"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "rate_limit": {
            "max_per_minute": rate_limiter.max_requests_per_minute,
            "current_requests": len(rate_limiter.requests),
            "can_request": rate_limiter.can_make_request()
        },
        "yfinance_version": yf.__version__
    }

@app.post("/api/subscribe")
async def subscribe(sub: Subscription):
    try:
        with open("/tmp/subscribers.txt", "a") as f:
            f.write(f"{sub.email},{datetime.now().isoformat()}\n")
        logger.info(f"📧 新訂閱: {sub.email}")
        return {"status": "success", "email": sub.email}
    except Exception as e:
        logger.error(f"訂閱失敗: {str(e)}")
        raise HTTPException(status_code=500, detail="訂閱失敗")

@app.get("/api/analyze", response_model=ComprehensiveResult)
async def single_analyze(symbol: str = Query(..., example="AAPL")):
    symbol = symbol.strip().upper()
    logger.info(f"🔍 分析請求: {symbol}")
    
    analyzer = BuffettAdvancedAnalyzer(symbol)
    result = await analyzer.analyze()
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"{symbol} 分析失敗：無法獲取有效數據。請檢查股票代號是否正確。"
        )
    
    return result

@app.get("/api/batch-analyze", response_model=List[ComprehensiveResult])
async def batch_analyze(
    symbols: str = Query(..., example="AAPL,MSFT,GOOGL,AMZN,TSLA")
):
    symbol_list = list(dict.fromkeys([s.strip().upper() for s in symbols.split(",") if s.strip()]))
    
    MAX_SYMBOLS = 8  # 降低批次限制
    if len(symbol_list) > MAX_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"單次最多 {MAX_SYMBOLS} 支股票。當前: {len(symbol_list)}"
        )
    
    logger.info(f"📊 批次分析 {len(symbol_list)} 支: {', '.join(symbol_list)}")
    
    results = []
    failed = []
    
    for idx, symbol in enumerate(symbol_list, 1):
        logger.info(f"[{idx}/{len(symbol_list)}] 分析 {symbol}")
        
        analyzer = BuffettAdvancedAnalyzer(symbol)
        analysis = await analyzer.analyze()
        
        if analysis:
            results.append(analysis)
        else:
            failed.append(symbol)
    
    logger.info(f"✅ 完成: 成功 {len(results)}, 失敗 {len(failed)}")
    
    if failed:
        logger.warning(f"失敗: {', '.join(failed)}")
    
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"所有股票分析失敗。失敗清單: {', '.join(failed)}"
        )
    
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    return results

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 Buffett Analyzer API v2.1 啟動")
    logger.info(f"📦 yfinance 版本: {yf.__version__}")
    logger.info(f"🚦 速率限制: {rate_limiter.max_requests_per_minute} req/min")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Buffett Analyzer API 關閉")
