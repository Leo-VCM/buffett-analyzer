"""
Buffett Analyzer API - 巴菲特量化分析系統後端
完整生產版本 v2.0
適用於 Render 免費方案部署
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
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==================== 初始化 ====================

app = FastAPI(
    title="Buffett Analyzer API", 
    version="2.0",
    description="巴菲特量化即時分析系統 - 完整生產版本",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境建議改為具體域名
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 快取設定
cache_path = "/tmp/yfinance_stock_cache"
CACHE_EXPIRE_SECONDS = int(os.environ.get("CACHE_EXPIRE", 3600))
session = requests_cache.CachedSession(
    cache_path, 
    expire_after=CACHE_EXPIRE_SECONDS, 
    backend='sqlite'
)

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 速率限制器 ====================

class RateLimiter:
    """智能速率限制器 - 防止觸發 Yahoo Finance API 限制"""
    
    def __init__(self):
        self.requests = []
        self.max_requests_per_minute = int(os.environ.get("MAX_REQUESTS_PER_MINUTE", 10))
        self.min_delay_between_requests = float(os.environ.get("MIN_DELAY_SECONDS", 0.5))
        
    def can_make_request(self) -> bool:
        """檢查是否可以發送請求"""
        now = datetime.now()
        # 清理 1 分鐘前的記錄
        self.requests = [req for req in self.requests if now - req < timedelta(minutes=1)]
        return len(self.requests) < self.max_requests_per_minute
    
    def record_request(self):
        """記錄請求時間"""
        self.requests.append(datetime.now())
    
    async def wait_if_needed(self):
        """如果需要，等待到可以發送請求"""
        wait_count = 0
        while not self.can_make_request():
            wait_count += 1
            if wait_count == 1:
                logger.warning("⚠️ 達到速率限制，等待中...")
            await asyncio.sleep(5)
        
        # 每次請求的最小間隔
        await asyncio.sleep(self.min_delay_between_requests)

rate_limiter = RateLimiter()

# ==================== 數據模型 ====================

class Subscription(BaseModel):
    """用戶訂閱模型"""
    email: str

class ComprehensiveResult(BaseModel):
    """完整的股票分析結果"""
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

# ==================== 核心分析引擎 ====================

class BuffettAdvancedAnalyzer:
    """巴菲特量化分析引擎"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.stock = yf.Ticker(self.symbol, session=session)

    def is_cached(self) -> bool:
        """檢查數據是否已快取"""
        cache_url = f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}"
        return session.cache.has_url(cache_url)

    async def analyze(self) -> Optional[dict]:
        """
        非同步分析股票（含速率限制保護）
        
        Returns:
            dict: 分析結果，失敗時返回 None
        """
        try:
            # 1. 檢查快取狀態
            is_cached = self.is_cached()
            
            if not is_cached:
                logger.info(f"🔍 {self.symbol} 未快取，準備發送新請求")
                # 等待速率限制器允許
                await rate_limiter.wait_if_needed()
                rate_limiter.record_request()
                
                # 額外隨機延遲（模擬人類行為）
                delay = random.uniform(0.3, 1.0)
                await asyncio.sleep(delay)
                logger.info(f"⏱️ 延遲 {delay:.2f}秒後請求 {self.symbol}")
            else:
                logger.info(f"✅ {self.symbol} 使用快取數據")

            # 2. 獲取基本資料
            info = self.stock.info
            
            # 檢查是否為有效股票
            if not info or 'symbol' not in info:
                logger.warning(f"❌ {self.symbol}: 無法獲取股票資訊")
                return None
            
            # 3. 獲取歷史數據
            hist = self.stock.history(period="1y")
            
            # 數據有效性檢查
            if hist.empty or len(hist) < 50:
                logger.warning(f"❌ {self.symbol}: 歷史數據不足（{len(hist)} 天）")
                return None

            # 4. 基本資訊提取
            company_name = info.get('longName') or info.get('shortName') or self.symbol
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                hist['Close'].iloc[-1]
            )
            
            if current_price <= 0:
                logger.warning(f"❌ {self.symbol}: 價格數據異常")
                return None
            
            # 5. 趨勢判斷 (MA200)
            ma200_period = min(200, len(hist))
            ma200 = hist['Close'].rolling(window=ma200_period).mean().iloc[-1]
            market_phase = "牛市 (Bull)" if current_price > ma200 else "熊市 (Bear)"

            # 6. 動能分析
            # 6個月動能（篩選用）
            six_months_idx = min(126, len(hist) - 1)
            six_months_ago = hist['Close'].iloc[-six_months_idx] if six_months_idx > 0 else hist['Close'].iloc[0]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
            is_positive_momentum = momentum_6m > 0

            # 1年動能（展示用）
            one_year_ago = hist['Close'].iloc[0]
            momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100

            # 7. 因子評分 (0-100 分制)
            
            # ROE (Return on Equity)
            roe = info.get('returnOnEquity', 0)
            norm_roe = (roe * 100) if abs(roe) < 1 else roe
            
            # P/E Ratio
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            pe = min(pe, 200) if pe > 0 else 0  # 限制極端值
            
            # 價值因子 (Value)
            if 0 < pe < 15:
                v_score = 100
            elif pe < 25:
                v_score = 70
            elif pe < 40:
                v_score = 40
            else:
                v_score = 20
            
            # 質量因子 (Quality)
            q_score = min(100, max(0, norm_roe * 4)) if norm_roe > 0 else 0
            
            # 動能因子 (Momentum)
            m_score = max(0, min(100, momentum_1y + 20))
            
            # 成長因子 (Growth)
            revenue_growth = info.get('revenueGrowth', 0)
            if revenue_growth:
                g_score = max(0, min(100, revenue_growth * 100))
            else:
                g_score = 50  # 預設中性值
            
            # 8. 綜合巴菲特分數（加權平均）
            buffett_score = (
                v_score * 0.4 +   # 價值 40%
                q_score * 0.3 +   # 質量 30%
                m_score * 0.2 +   # 動能 20%
                g_score * 0.1     # 成長 10%
            )

            # 9. 最終分數（加入懲罰機制）
            final_score = buffett_score
            
            # 負動能懲罰
            if not is_positive_momentum:
                final_score *= 0.5
                logger.info(f"  ⚠️ {self.symbol} 負動能懲罰: {buffett_score:.1f} → {final_score:.1f}")
            
            # 熊市懲罰
            if market_phase == "熊市 (Bear)":
                final_score *= 0.8
                logger.info(f"  ⚠️ {self.symbol} 熊市懲罰: {buffett_score:.1f} → {final_score:.1f}")

            # 10. 風險評估
            
            # 債務風險
            debt_to_equity = info.get('debtToEquity', 0)
            debt_r = min(100, (debt_to_equity / 2)) if debt_to_equity else 0
            
            # 估值風險
            val_r = min(100, (pe / 40) * 100) if pe > 0 else 50
            
            # 波動性風險
            returns = hist['Close'].pct_change().dropna()
            if len(returns) > 0:
                vol_r = returns.std() * np.sqrt(252) * 100  # 年化波動率
            else:
                vol_r = 50
            
            # 總風險（三項平均）
            total_risk = (debt_r + val_r + vol_r) / 3

            # 11. 投資建議
            if final_score > 70:
                recommendation = "強力推薦"
            elif final_score > 40:
                recommendation = "觀察"
            else:
                recommendation = "避開"

            logger.info(f"✅ {self.symbol} 分析完成 (評分: {buffett_score:.1f}, 建議: {recommendation})")

            # 12. 返回完整結果
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
                    "momentum_6m": round(float(momentum_6m), 2),
                    "cached": is_cached
                }
            }
            
        except Exception as e:
            logger.error(f"❌ {self.symbol} 分析失敗: {str(e)}", exc_info=True)
            return None

# ==================== API 端點 ====================

@app.get("/")
async def root():
    """根路徑 - API 說明"""
    return {
        "service": "Buffett Analyzer API",
        "version": "2.0",
        "status": "operational",
        "description": "巴菲特量化即時分析系統",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "single_analyze": "/api/analyze?symbol=AAPL",
            "batch_analyze": "/api/batch-analyze?symbols=AAPL,MSFT,GOOGL",
            "cache_stats": "/cache/stats",
            "subscribe": "/api/subscribe (POST)"
        },
        "documentation": "訪問 /docs 查看完整 API 文檔"
    }

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    cache_exists = os.path.exists(cache_path)
    
    # 統計快取項目數
    cache_size = 0
    if cache_exists:
        try:
            import sqlite3
            conn = sqlite3.connect(f"{cache_path}.sqlite")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM responses")
            cache_size = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.error(f"讀取快取統計失敗: {e}")
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache": {
            "path": cache_path,
            "exists": cache_exists,
            "size": cache_size,
            "expire_seconds": CACHE_EXPIRE_SECONDS
        },
        "rate_limit": {
            "max_per_minute": rate_limiter.max_requests_per_minute,
            "current_requests": len(rate_limiter.requests),
            "can_request": rate_limiter.can_make_request()
        }
    }

@app.post("/api/subscribe")
async def subscribe(sub: Subscription):
    """用戶訂閱服務"""
    try:
        # 儲存到檔案（生產環境建議改用資料庫）
        with open("/tmp/subscribers.txt", "a") as f:
            f.write(f"{sub.email},{datetime.now().isoformat()}\n")
        logger.info(f"📧 新訂閱: {sub.email}")
        return {
            "status": "success",
            "message": "訂閱成功",
            "email": sub.email
        }
    except Exception as e:
        logger.error(f"訂閱失敗: {str(e)}")
        raise HTTPException(status_code=500, detail="訂閱失敗，請稍後再試")

@app.get("/api/analyze", response_model=ComprehensiveResult)
async def single_analyze(
    symbol: str = Query(..., description="股票代號", example="AAPL")
):
    """
    單一股票分析
    
    - **symbol**: 股票代號（如 AAPL, MSFT, GOOGL）
    """
    symbol = symbol.strip().upper()
    logger.info(f"🔍 單一分析請求: {symbol}")
    
    analyzer = BuffettAdvancedAnalyzer(symbol)
    result = await analyzer.analyze()
    
    if not result:
        logger.warning(f"❌ {symbol} 分析失敗")
        raise HTTPException(
            status_code=404, 
            detail=f"{symbol} 分析失敗：可能數據不足、代號錯誤或 API 暫時無法訪問"
        )
    
    return result

@app.get("/api/batch-analyze", response_model=List[ComprehensiveResult])
async def batch_analyze(
    symbols: str = Query(
        ..., 
        description="逗號分隔的股票代號",
        example="AAPL,MSFT,GOOGL,AMZN,TSLA"
    )
):
    """
    批次分析多支股票
    
    - **symbols**: 逗號分隔的股票代號（如 AAPL,MSFT,GOOGL）
    - 單次最多支援 10 支股票（可透過環境變數 MAX_SYMBOLS 調整）
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    
    # 去重
    symbol_list = list(dict.fromkeys(symbol_list))
    
    # 限制單次請求數量
    MAX_SYMBOLS = int(os.environ.get("MAX_SYMBOLS", 10))
    if len(symbol_list) > MAX_SYMBOLS:
        raise HTTPException(
            status_code=400, 
            detail=f"單次最多分析 {MAX_SYMBOLS} 支股票（避免速率限制）。當前請求: {len(symbol_list)} 支"
        )
    
    logger.info(f"📊 開始批次分析 {len(symbol_list)} 支股票: {', '.join(symbol_list)}")
    
    results = []
    cached_count = 0
    failed_symbols = []
    
    # 逐一分析（含速率限制保護）
    for idx, symbol in enumerate(symbol_list, 1):
        logger.info(f"[{idx}/{len(symbol_list)}] 分析 {symbol}...")
        
        analyzer = BuffettAdvancedAnalyzer(symbol)
        analysis = await analyzer.analyze()
        
        if analysis:
            results.append(analysis)
            if analysis['details'].get('cached'):
                cached_count += 1
        else:
            failed_symbols.append(symbol)
            logger.warning(f"❌ {symbol} 分析失敗")
    
    logger.info(
        f"✅ 批次分析完成: "
        f"成功 {len(results)}/{len(symbol_list)}, "
        f"快取 {cached_count}, "
        f"失敗 {len(failed_symbols)}"
    )
    
    if failed_symbols:
        logger.warning(f"失敗的股票: {', '.join(failed_symbols)}")
    
    # 如果全部失敗，返回 404
    if not results:
        raise HTTPException(
            status_code=404, 
            detail=f"所有股票分析失敗。失敗的股票: {', '.join(failed_symbols)}。可能原因: 代號錯誤、數據不足或 API 暫時無法訪問"
        )
    
    # 按 buffettScore 降序排序
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    
    return results

@app.get("/cache/stats")
async def cache_stats():
    """快取統計資訊"""
    try:
        import sqlite3
        conn = sqlite3.connect(f"{cache_path}.sqlite")
        cursor = conn.cursor()
        
        # 獲取快取項目
        cursor.execute("SELECT key, created_at FROM responses ORDER BY created_at DESC LIMIT 10")
        rows = cursor.fetchall()
        cached_items = [{"url": row[0], "created_at": row[1]} for row in rows]
        
        cursor.execute("SELECT COUNT(*) FROM responses")
        total_cached = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_cached_requests": total_cached,
            "cache_expire_seconds": CACHE_EXPIRE_SECONDS,
            "recent_cached_items": cached_items
        }
    except Exception as e:
        logger.error(f"讀取快取統計失敗: {e}")
        return {
            "error": str(e),
            "message": "無法讀取快取統計"
        }

@app.get("/cache/clear")
async def clear_cache():
    """清除所有快取（調試用）"""
    try:
        session.cache.clear()
        logger.info("🗑️ 快取已清除")
        return {
            "status": "success",
            "message": "快取已清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清除快取失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清除快取失敗: {str(e)}")

# ==================== 啟動事件 ====================

@app.on_event("startup")
async def startup_event():
    """應用啟動時執行"""
    logger.info("=" * 60)
    logger.info("🚀 Buffett Analyzer API 啟動中...")
    logger.info(f"📍 快取路徑: {cache_path}")
    logger.info(f"⏱️ 快取過期時間: {CACHE_EXPIRE_SECONDS} 秒")
    logger.info(f"🚦 速率限制: {rate_limiter.max_requests_per_minute} 請求/分鐘")
    logger.info(f"📊 最大批次股票數: {os.environ.get('MAX_SYMBOLS', 10)}")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉時執行"""
    logger.info("👋 Buffett Analyzer API 關閉中...")
