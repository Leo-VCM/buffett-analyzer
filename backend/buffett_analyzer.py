"""
Buffett Stock Picker - 巴菲特選股系統
按產業分類，篩選出符合巴菲特標準的 25 支股票池
"""
import os
import logging
import random
import asyncio
from typing import List, Optional, Dict
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
    title="Buffett Stock Picker API", 
    version="3.0",
    description="巴菲特選股系統 - 三大產業股票池分析",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 股票池定義 ====================

STOCK_POOLS = {
    "科技股": {
        "description": "科技創新類股票",
        "symbols": [
            # 大型科技股
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            # 軟體與雲端
            "CRM", "ADBE", "ORCL", "SAP", "SNOW", "PLTR",
            # 半導體
            "INTC", "QCOM", "AVGO", "TSM", "ASML",
            # 電商與網路
            "BABA", "JD", "SHOP", "SE"
        ]
    },
    "金融股": {
        "description": "銀行、保險與金融服務",
        "symbols": [
            # 銀行
            "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC",
            # 保險
            "BRK.B", "AIG", "MET", "PRU", "AFL", "ALL",
            # 金融科技
            "V", "MA", "PYPL", "SQ", "AXP",
            # 資產管理
            "BLK", "SCHW", "BX", "KKR"
        ]
    },
    "民生消費股": {
        "description": "日常消費與零售",
        "symbols": [
            # 零售
            "WMT", "HD", "COST", "TGT", "LOW", "TJX",
            # 食品飲料
            "KO", "PEP", "MDLZ", "KHC", "GIS", "K",
            # 餐飲
            "MCD", "SBUX", "YUM", "CMG", "QSR",
            # 日用品
            "PG", "UL", "CL", "KMB", "CLX",
            # 醫療保健
            "JNJ", "PFE", "UNH"
        ]
    }
}

# ==================== 速率限制器 ====================

class RateLimiter:
    def __init__(self):
        self.requests = []
        self.max_requests_per_minute = 15  # 提高到15次
        self.min_delay_between_requests = 0.3
        
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
            await asyncio.sleep(5)
        await asyncio.sleep(self.min_delay_between_requests)

rate_limiter = RateLimiter()

# ==================== 數據模型 ====================

class StockAnalysis(BaseModel):
    symbol: str
    companyName: str
    sector: str  # 產業分類
    buffettScore: float
    currentPrice: float
    momentum: float
    totalRisk: float
    roe: float
    pe: float
    recommendation: str
    marketPhase: str
    factors: dict
    risks: dict
    buffettCriteria: dict  # 巴菲特標準評估
    details: dict

class SectorAnalysis(BaseModel):
    sector: str
    description: str
    total_stocks: int
    analyzed_stocks: int
    top_picks: List[StockAnalysis]
    average_score: float
    sector_risk: str

# ==================== 巴菲特選股引擎 ====================

class BuffettStockPicker:
    """巴菲特選股引擎 - 基於價值投資原則"""
    
    # 巴菲特的核心標準
    BUFFETT_CRITERIA = {
        "roe_threshold": 15,          # ROE > 15%
        "pe_max": 25,                 # P/E < 25
        "debt_to_equity_max": 100,    # 債務權益比 < 100%
        "profit_margin_min": 10,      # 利潤率 > 10%
        "consistent_earnings": True,   # 穩定盈利
        "moat": True,                 # 護城河（品牌、專利等）
    }
    
    def __init__(self, symbol: str, sector: str):
        self.symbol = symbol.upper()
        self.sector = sector
        self.stock = yf.Ticker(self.symbol, session=session)

    def is_cached(self) -> bool:
        cache_url = f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}"
        return session.cache.has_url(cache_url)

    async def analyze(self) -> Optional[dict]:
        """完整分析股票"""
        try:
            is_cached = self.is_cached()
            
            if not is_cached:
                logger.info(f"🔍 {self.symbol} ({self.sector}) 未快取")
                await rate_limiter.wait_if_needed()
                rate_limiter.record_request()
                await asyncio.sleep(random.uniform(0.2, 0.8))
            else:
                logger.info(f"✅ {self.symbol} ({self.sector}) 使用快取")

            # 獲取數據
            try:
                info = self.stock.info
                hist = self.stock.history(period="1y")
            except Exception as e:
                logger.error(f"❌ {self.symbol}: 數據獲取失敗 - {e}")
                return None
            
            if not info or hist.empty or len(hist) < 50:
                logger.warning(f"❌ {self.symbol}: 數據不足")
                return None

            # 基本資訊
            company_name = info.get('longName') or info.get('shortName') or self.symbol
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                hist['Close'].iloc[-1]
            )
            
            if not current_price or current_price <= 0:
                return None

            # 財務指標
            roe = info.get('returnOnEquity', 0)
            norm_roe = (roe * 100) if abs(roe) < 1 else roe
            
            pe = info.get('forwardPE') or info.get('trailingPE') or 25
            pe = min(pe, 200) if pe > 0 else 25
            
            profit_margin = info.get('profitMargins', 0) * 100
            debt_to_equity = info.get('debtToEquity', 0)
            
            # 市場分析
            ma200 = hist['Close'].rolling(window=min(200, len(hist))).mean().iloc[-1]
            market_phase = "牛市" if current_price > ma200 else "熊市"
            
            # 動能
            one_year_ago = hist['Close'].iloc[0]
            momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100
            
            six_months_idx = min(126, len(hist) - 1)
            six_months_ago = hist['Close'].iloc[-six_months_idx]
            momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
            is_positive_momentum = momentum_6m > 0

            # 巴菲特標準評估
            buffett_criteria = {
                "high_roe": norm_roe >= self.BUFFETT_CRITERIA["roe_threshold"],
                "reasonable_pe": 0 < pe <= self.BUFFETT_CRITERIA["pe_max"],
                "low_debt": debt_to_equity <= self.BUFFETT_CRITERIA["debt_to_equity_max"],
                "profitable": profit_margin >= self.BUFFETT_CRITERIA["profit_margin_min"],
                "positive_momentum": is_positive_momentum
            }
            
            criteria_passed = sum(buffett_criteria.values())
            buffett_grade = "A+" if criteria_passed >= 5 else "A" if criteria_passed >= 4 else "B" if criteria_passed >= 3 else "C"

            # 因子評分
            v_score = 100 if 0 < pe < 15 else 70 if pe < 25 else 40
            q_score = min(100, max(0, norm_roe * 4))
            m_score = max(0, min(100, momentum_1y + 20))
            g_score = max(0, min(100, info.get('revenueGrowth', 0) * 100)) if info.get('revenueGrowth') else 50
            
            # 產業加權（巴菲特偏好）
            sector_weights = {
                "金融股": {"quality": 1.2, "value": 1.1},  # 巴菲特最愛
                "民生消費股": {"quality": 1.1, "value": 1.0},
                "科技股": {"growth": 1.2, "momentum": 1.1}
            }
            
            weight = sector_weights.get(self.sector, {})
            v_score *= weight.get("value", 1.0)
            q_score *= weight.get("quality", 1.0)
            m_score *= weight.get("momentum", 1.0)
            g_score *= weight.get("growth", 1.0)

            # 綜合評分
            buffett_score = (
                v_score * 0.35 +  # 價值 35%
                q_score * 0.35 +  # 質量 35%
                m_score * 0.15 +  # 動能 15%
                g_score * 0.15    # 成長 15%
            )
            
            # 巴菲特標準加成
            if criteria_passed >= 4:
                buffett_score *= 1.2
            elif criteria_passed >= 3:
                buffett_score *= 1.1

            # 最終分數
            final_score = buffett_score
            if not is_positive_momentum:
                final_score *= 0.7
            if market_phase == "熊市":
                final_score *= 0.85

            # 風險評估
            debt_r = min(100, debt_to_equity / 2) if debt_to_equity else 20
            val_r = min(100, (pe / 40) * 100)
            returns = hist['Close'].pct_change().dropna()
            vol_r = returns.std() * np.sqrt(252) * 100 if len(returns) > 0 else 50
            total_risk = (debt_r + val_r + vol_r) / 3

            # 投資建議
            if final_score > 80 and criteria_passed >= 4:
                recommendation = "強力推薦 ⭐⭐⭐"
            elif final_score > 65 and criteria_passed >= 3:
                recommendation = "推薦 ⭐⭐"
            elif final_score > 50:
                recommendation = "觀察 ⭐"
            else:
                recommendation = "避開"

            logger.info(f"✅ {self.symbol} ({self.sector}) 評分: {buffett_score:.1f}, 標準: {criteria_passed}/5, 等級: {buffett_grade}")

            return {
                "symbol": self.symbol,
                "companyName": company_name,
                "sector": self.sector,
                "buffettScore": round(float(buffett_score), 1),
                "currentPrice": round(float(current_price), 2),
                "momentum": round(float(momentum_1y), 2),
                "totalRisk": round(float(total_risk), 1),
                "roe": round(float(norm_roe), 2),
                "pe": round(float(pe), 2),
                "recommendation": recommendation,
                "marketPhase": market_phase,
                "factors": {
                    "value": int(round(min(100, v_score))),
                    "quality": int(round(min(100, q_score))),
                    "momentum": int(round(m_score)),
                    "growth": int(round(g_score))
                },
                "risks": {
                    "debt": round(float(debt_r), 1),
                    "valuation": round(float(val_r), 1),
                    "volatility": round(float(vol_r), 1)
                },
                "buffettCriteria": {
                    "grade": buffett_grade,
                    "criteria_passed": criteria_passed,
                    "details": {
                        "high_roe": f"{'✅' if buffett_criteria['high_roe'] else '❌'} ROE {norm_roe:.1f}% {'≥' if buffett_criteria['high_roe'] else '<'} 15%",
                        "reasonable_pe": f"{'✅' if buffett_criteria['reasonable_pe'] else '❌'} P/E {pe:.1f} {'≤' if buffett_criteria['reasonable_pe'] else '>'} 25",
                        "low_debt": f"{'✅' if buffett_criteria['low_debt'] else '❌'} 債務比 {debt_to_equity:.1f}% {'≤' if buffett_criteria['low_debt'] else '>'} 100%",
                        "profitable": f"{'✅' if buffett_criteria['profitable'] else '❌'} 利潤率 {profit_margin:.1f}% {'≥' if buffett_criteria['profitable'] else '<'} 10%",
                        "positive_momentum": f"{'✅' if buffett_criteria['positive_momentum'] else '❌'} 6個月動能 {momentum_6m:.1f}%"
                    }
                },
                "details": {
                    "ma200": round(float(ma200), 2),
                    "profit_margin": round(float(profit_margin), 2),
                    "debt_to_equity": round(float(debt_to_equity), 1),
                    "cached": is_cached
                }
            }
            
        except Exception as e:
            logger.error(f"❌ {self.symbol} 分析失敗: {str(e)}")
            return None

# ==================== API 端點 ====================

@app.get("/")
async def root():
    return {
        "service": "Buffett Stock Picker API",
        "version": "3.0",
        "description": "巴菲特選股系統 - 三大產業股票池分析",
        "sectors": list(STOCK_POOLS.keys()),
        "total_stocks": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
        "endpoints": {
            "all_sectors": "/api/stock-pool",
            "specific_sector": "/api/stock-pool?sector=科技股",
            "top_25": "/api/top-25",
            "analyze_symbol": "/api/analyze?symbol=AAPL"
        }
    }

@app.get("/api/stock-pool")
async def get_stock_pool(
    sector: Optional[str] = Query(None, description="產業分類（科技股/金融股/民生消費股）"),
    limit: int = Query(10, description="每個產業返回的股票數量")
):
    """
    獲取股票池分析
    - 不指定 sector：返回所有產業
    - 指定 sector：返回特定產業
    """
    
    sectors_to_analyze = [sector] if sector and sector in STOCK_POOLS else list(STOCK_POOLS.keys())
    
    results = []
    
    for sector_name in sectors_to_analyze:
        pool = STOCK_POOLS[sector_name]
        symbols = pool["symbols"]
        
        logger.info(f"📊 開始分析 {sector_name}: {len(symbols)} 支股票")
        
        sector_results = []
        for symbol in symbols:
            picker = BuffettStockPicker(symbol, sector_name)
            analysis = await picker.analyze()
            if analysis:
                sector_results.append(analysis)
        
        # 排序並取前 N 名
        sector_results.sort(key=lambda x: x['buffettScore'], reverse=True)
        top_stocks = sector_results[:limit]
        
        # 產業統計
        avg_score = sum(s['buffettScore'] for s in sector_results) / len(sector_results) if sector_results else 0
        avg_risk = sum(s['totalRisk'] for s in sector_results) / len(sector_results) if sector_results else 0
        
        sector_risk = "低風險" if avg_risk < 35 else "中風險" if avg_risk < 55 else "高風險"
        
        results.append({
            "sector": sector_name,
            "description": pool["description"],
            "total_stocks": len(symbols),
            "analyzed_stocks": len(sector_results),
            "top_picks": top_stocks,
            "average_score": round(avg_score, 1),
            "average_risk": round(avg_risk, 1),
            "sector_risk": sector_risk
        })
    
    return results

@app.get("/api/top-25")
async def get_top_25():
    """
    巴菲特的 25 支股票池
    從三大產業中選出評分最高的 25 支股票
    """
    
    logger.info("🎯 開始篩選巴菲特 TOP 25 股票池...")
    
    all_stocks = []
    
    # 分析所有股票
    for sector_name, pool in STOCK_POOLS.items():
        logger.info(f"📊 分析 {sector_name}...")
        
        for symbol in pool["symbols"]:
            picker = BuffettStockPicker(symbol, sector_name)
            analysis = await picker.analyze()
            if analysis:
                all_stocks.append(analysis)
    
    # 按評分排序
    all_stocks.sort(key=lambda x: x['buffettScore'], reverse=True)
    
    # 取前 25 名
    top_25 = all_stocks[:25]
    
    # 統計分析
    sectors_count = {}
    total_score = 0
    total_risk = 0
    high_grade_count = 0
    
    for stock in top_25:
        sectors_count[stock['sector']] = sectors_count.get(stock['sector'], 0) + 1
        total_score += stock['buffettScore']
        total_risk += stock['totalRisk']
        if stock['buffettCriteria']['grade'] in ['A+', 'A']:
            high_grade_count += 1
    
    return {
        "title": "巴菲特 TOP 25 股票池",
        "description": "基於價值投資原則篩選的優質股票",
        "total_analyzed": len(all_stocks),
        "top_25_stocks": top_25,
        "statistics": {
            "average_score": round(total_score / 25, 1),
            "average_risk": round(total_risk / 25, 1),
            "high_grade_stocks": high_grade_count,
            "sector_distribution": sectors_count
        },
        "criteria": BuffettStockPicker.BUFFETT_CRITERIA,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/analyze")
async def analyze_single_stock(
    symbol: str = Query(..., description="股票代號"),
    sector: str = Query("科技股", description="產業分類")
):
    """單一股票分析"""
    picker = BuffettStockPicker(symbol.upper(), sector)
    result = await picker.analyze()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"{symbol} 分析失敗")
    
    return result

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "sectors": len(STOCK_POOLS),
        "total_stocks": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
        "cache_expire": CACHE_EXPIRE_SECONDS
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
