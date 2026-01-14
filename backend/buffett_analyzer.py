"""
Buffett Stock Picker - 巴菲特選股系統 (優化版)
按產業分類,篩選出符合巴菲特標準的 25 支股票池
"""
import os
import logging
import random
import asyncio
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from functools import lru_cache
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import time

# ==================== 配置管理 ====================

class Config:
    """集中管理所有配置參數"""
    # 快取設定
    CACHE_PATH = "/tmp/yfinance_stock_cache"
    CACHE_EXPIRE_SECONDS = int(os.environ.get("CACHE_EXPIRE", 3600))
    
    # 速率限制
    MAX_REQUESTS_PER_MINUTE = 20  # 提高到 20
    MIN_REQUEST_DELAY = 0.2  # 降低延遲
    
    # 資料要求
    MIN_HISTORY_DAYS = 20
    MIN_INFO_FIELDS = 5
    
    # 並行控制
    MAX_CONCURRENT_REQUESTS = 10  # 限制同時並行數
    
    # API 設定
    API_TITLE = "Buffett Stock Picker API"
    API_VERSION = "3.1"
    API_DESCRIPTION = "巴菲特選股系統 - 三大產業股票池分析 (優化版)"

config = Config()

# ==================== 日誌配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 快取與啟動管理 ====================

session = requests_cache.CachedSession(
    config.CACHE_PATH,
    expire_after=config.CACHE_EXPIRE_SECONDS,
    backend='sqlite'
)

START_TIME = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    logger.info("🚀 巴菲特選股系統啟動中...")
    logger.info(f"📊 快取過期時間: {config.CACHE_EXPIRE_SECONDS}秒")
    yield
    logger.info("👋 系統正在關閉...")

# ==================== FastAPI 初始化 ====================

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ==================== 股票池定義 ====================

STOCK_POOLS = {
    "科技股": {
        "description": "科技創新類股票",
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            "CRM", "ADBE", "ORCL", "SAP", "SNOW", "PLTR",
            "INTC", "QCOM", "AVGO", "TSM", "ASML",
            "BABA", "JD", "SHOP", "SE"
        ]
    },
    "金融股": {
        "description": "銀行、保險與金融服務",
        "symbols": [
            "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC",
            "BRK.B", "AIG", "MET", "PRU", "AFL", "ALL",
            "V", "MA", "PYPL", "SQ", "AXP",
            "BLK", "SCHW", "BX", "KKR"
        ]
    },
    "民生消費股": {
        "description": "日常消費與零售",
        "symbols": [
            "WMT", "HD", "COST", "TGT", "LOW", "TJX",
            "KO", "PEP", "MDLZ", "KHC", "GIS", "K",
            "MCD", "SBUX", "YUM", "CMG", "QSR",
            "PG", "UL", "CL", "KMB", "CLX",
            "JNJ", "PFE", "UNH"
        ]
    }
}

# ==================== 優化的速率限制器 ====================

class RateLimiter:
    """改進的速率限制器,支援並行控制"""
    
    def __init__(self):
        self.requests = []
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        
    def _clean_old_requests(self):
        """清理過期的請求記錄"""
        now = datetime.now()
        self.requests = [
            req for req in self.requests 
            if now - req < timedelta(minutes=1)
        ]
    
    def can_make_request(self) -> bool:
        """檢查是否可以發送請求"""
        self._clean_old_requests()
        return len(self.requests) < config.MAX_REQUESTS_PER_MINUTE
    
    def record_request(self):
        """記錄請求時間"""
        self.requests.append(datetime.now())
    
    async def wait_if_needed(self):
        """智能等待機制"""
        wait_count = 0
        while not self.can_make_request():
            wait_count += 1
            if wait_count == 1:
                logger.warning("⚠️ 達到速率限制,等待中...")
            await asyncio.sleep(3)  # 縮短等待時間
        
        # 添加隨機延遲避免突發請求
        await asyncio.sleep(random.uniform(0.1, config.MIN_REQUEST_DELAY))

rate_limiter = RateLimiter()

# ==================== 數據模型 (增強驗證) ====================

class StockAnalysis(BaseModel):
    symbol: str
    companyName: str
    sector: str
    buffettScore: float = Field(ge=0, le=100)
    currentPrice: float = Field(gt=0)
    momentum: float
    totalRisk: float = Field(ge=0, le=100)
    roe: float
    pe: float | str
    recommendation: str
    marketPhase: str
    factors: Dict[str, int]
    risks: Dict[str, float]
    buffettCriteria: Dict
    details: Dict
    
    @validator('pe')
    def validate_pe(cls, v):
        """驗證 P/E 值"""
        if isinstance(v, str):
            return v
        if v < 0:
            return "N/A"
        return v

class SectorAnalysis(BaseModel):
    sector: str
    description: str
    total_stocks: int
    analyzed_stocks: int
    top_picks: List[StockAnalysis]
    average_score: float
    average_risk: float
    sector_risk: str

# ==================== 資料獲取優化 ====================

class DataFetcher:
    """優化的資料獲取器"""
    
    @staticmethod
    async def fetch_stock_data(symbol: str) -> Tuple[Optional[dict], Optional[pd.DataFrame]]:
        """非同步獲取股票資料,帶重試機制"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(symbol, session=session)
                
                # 使用 fast_info 作為備選方案
                try:
                    info = stock.info
                except Exception:
                    logger.warning(f"⚠️ {symbol}: info 失敗,嘗試 fast_info")
                    info = stock.fast_info.__dict__ if hasattr(stock, 'fast_info') else {}
                
                # 獲取歷史數據
                hist = stock.history(period="1y", auto_adjust=True)
                
                # 驗證數據完整性
                if not info or len(info) < config.MIN_INFO_FIELDS:
                    logger.warning(f"❌ {symbol}: 基本面資料不足")
                    return None, None
                
                if hist.empty or len(hist) < config.MIN_HISTORY_DAYS:
                    logger.warning(f"❌ {symbol}: 歷史數據不足")
                    return None, None
                
                return info, hist
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ {symbol}: 第{attempt + 1}次嘗試失敗,重試中... ({e})")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"❌ {symbol}: 所有嘗試失敗 - {e}")
                    return None, None
    
    @staticmethod
    def normalize_financial_metrics(info: dict) -> Dict[str, float]:
        """標準化財務指標"""
        # ROE 處理
        raw_roe = info.get('returnOnEquity')
        roe = (raw_roe * 100 if raw_roe and abs(raw_roe) < 1 else raw_roe) if raw_roe else 0
        
        # P/E 處理
        pe = info.get('forwardPE') or info.get('trailingPE')
        pe = min(pe, 500) if pe and pe > 0 else 999
        
        # 淨利率
        margin = info.get('profitMargins')
        profit_margin = (margin * 100) if margin else 0
        
        # 債務權益比
        raw_d_e = info.get('debtToEquity')
        debt_to_equity = (raw_d_e if raw_d_e < 5 else raw_d_e / 100) if raw_d_e else 2.0
        
        # 營收成長
        rev_growth = (info.get('revenueGrowth', 0) or 0) * 100
        
        return {
            'roe': roe,
            'pe': pe,
            'profit_margin': profit_margin,
            'debt_to_equity': debt_to_equity,
            'revenue_growth': rev_growth
        }

# ==================== 巴菲特選股引擎 (優化版) ====================

class BuffettStockPicker:
    """優化的巴菲特選股引擎"""
    
    BUFFETT_CRITERIA = {
        "roe": {"threshold": 15, "label": "股東權益報酬率 (ROE)", "unit": "%", "operator": ">="},
        "pe": {"threshold": 25, "label": "本益比 (P/E)", "unit": "", "operator": "<="},
        "debt_to_equity": {"threshold": 1.0, "label": "債務權益比", "unit": "", "operator": "<="},
        "profit_margin": {"threshold": 10, "label": "淨利率", "unit": "%", "operator": ">="},
    }
    
    SECTOR_WEIGHTS = {
        "金融股": {"quality": 1.15, "value": 1.1},
        "民生消費股": {"quality": 1.1, "value": 1.05},
        "科技股": {"growth": 1.15, "momentum": 1.05}
    }
    
    def __init__(self, symbol: str, sector: str):
        self.symbol = symbol.upper()
        self.sector = sector
        self.data_fetcher = DataFetcher()
    
    def _calculate_momentum(self, hist: pd.DataFrame, current_price: float) -> Dict[str, float]:
        """計算多時間框架動能"""
        try:
            momentum = {}
            
            # 確保有足夠的資料
            if len(hist) < 21:
                return {'1y': 0, '6m': 0, '1m': 0}
            
            # 一年動能
            one_year_ago = hist['Close'].iloc[0]
            momentum['1y'] = ((current_price - one_year_ago) / one_year_ago) * 100
            
            # 六個月動能
            half_year_idx = max(0, len(hist) // 2)
            six_months_ago = hist['Close'].iloc[half_year_idx]
            momentum['6m'] = ((current_price - six_months_ago) / six_months_ago) * 100
            
            # 一個月動能
            one_month_idx = max(0, len(hist) - 21)
            one_month_ago = hist['Close'].iloc[one_month_idx]
            momentum['1m'] = ((current_price - one_month_ago) / one_month_ago) * 100
            
            return momentum
            
        except Exception as e:
            logger.warning(f"⚠️ {self.symbol} 動能計算失敗: {e}")
            return {'1y': 0, '6m': 0, '1m': 0}
    
    def _calculate_technical_indicators(self, hist: pd.DataFrame) -> Dict[str, float]:
        """計算技術指標"""
        ma200 = hist['Close'].rolling(window=200, min_periods=1).mean().iloc[-1]
        ma50 = hist['Close'].rolling(window=50, min_periods=1).mean().iloc[-1]
        
        return {
            'ma200': ma200,
            'ma50': ma50
        }
    
    def _assess_market_phase(self, current_price: float, ma200: float, ma50: float) -> str:
        """評估市場階段"""
        if current_price > ma200:
            return "多頭排列" if current_price > ma50 else "高檔震盪"
        else:
            return "空頭趨勢" if current_price < ma50 else "低檔打底"
    
    def _calculate_factor_scores(self, metrics: dict, momentum: dict) -> Dict[str, int]:
        """計算四大因子評分"""
        pe = metrics['pe']
        roe = metrics['roe']
        rev_growth = metrics['revenue_growth']
        
        # Value Score
        v_score = 0 if pe >= 999 else (
            100 if pe < 12 else 80 if pe < 20 else 50 if pe < 30 else 20
        )
        
        # Quality Score
        q_score = min(100, max(0, roe * 4))
        
        # Momentum Score
        m_score = max(0, min(100, (momentum['1y'] * 0.4 + momentum['6m'] * 0.6) + 50))
        
        # Growth Score
        g_score = min(100, max(0, rev_growth * 2 + 50)) if rev_growth != 0 else 60
        
        # 應用產業權重
        weight = self.SECTOR_WEIGHTS.get(self.sector, {})
        v_score = min(100, v_score * weight.get("value", 1.0))
        q_score = min(100, q_score * weight.get("quality", 1.0))
        m_score = min(100, m_score * weight.get("momentum", 1.0))
        g_score = min(100, g_score * weight.get("growth", 1.0))
        
        return {
            'value': int(round(v_score)),
            'quality': int(round(q_score)),
            'momentum': int(round(m_score)),
            'growth': int(round(g_score))
        }
    
    def _calculate_buffett_score(
        self, 
        factor_scores: dict, 
        criteria_passed: int, 
        is_positive_momentum: bool,
        market_phase: str
    ) -> float:
        """計算最終巴菲特評分"""
        # 基礎評分
        base_score = (
            factor_scores['value'] * 0.35 +
            factor_scores['quality'] * 0.35 +
            factor_scores['momentum'] * 0.15 +
            factor_scores['growth'] * 0.15
        )
        
        # 標準加成
        if criteria_passed >= 4:
            base_score *= 1.15
        elif criteria_passed >= 3:
            base_score *= 1.05
        
        # 趨勢調整
        final_score = base_score
        if not is_positive_momentum:
            final_score *= 0.75
        if market_phase == "空頭趨勢":
            final_score *= 0.85
        
        return max(0, min(100, final_score))
    
    def _calculate_risk_score(
        self, 
        metrics: dict, 
        hist: pd.DataFrame
    ) -> Tuple[float, Dict[str, float]]:
        """計算風險評分"""
        # 債務風險
        debt_r = min(100, metrics['debt_to_equity'] * 50)
        
        # 估值風險
        pe = metrics['pe']
        val_r = 100 if pe >= 100 else (pe / 40) * 100
        
        # 波動風險
        returns = hist['Close'].pct_change().dropna()
        vol_r = (returns.std() * np.sqrt(252) * 100) if len(returns) > 20 else 50
        
        # 綜合風險
        total_risk = min(100, debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2)
        
        return total_risk, {
            'debt': round(debt_r, 1),
            'valuation': round(val_r, 1),
            'volatility': round(vol_r, 1)
        }
    
    async def analyze(self) -> Optional[dict]:
        """執行完整分析"""
        try:
            # 控制並行數量
            async with rate_limiter.semaphore:
                # 檢查快取
                is_cached = session.cache.has_url(
                    f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}"
                )
                
                if not is_cached:
                    await rate_limiter.wait_if_needed()
                    rate_limiter.record_request()
                
                # 獲取資料
                info, hist = await self.data_fetcher.fetch_stock_data(self.symbol)
                
                if not info or hist is None:
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
                
                # 標準化財務指標
                metrics = self.data_fetcher.normalize_financial_metrics(info)
                
                # 計算動能
                momentum = self._calculate_momentum(hist, current_price)
                
                # 技術指標
                tech_indicators = self._calculate_technical_indicators(hist)
                
                # 市場階段
                market_phase = self._assess_market_phase(
                    current_price, 
                    tech_indicators['ma200'], 
                    tech_indicators['ma50']
                )
                
                # 巴菲特標準檢查
                is_positive_momentum = momentum['6m'] > 0 and momentum['1m'] > -5
                
                buffett_criteria = {
                    "high_roe": metrics['roe'] >= self.BUFFETT_CRITERIA["roe"]["threshold"],
                    "reasonable_pe": 0 < metrics['pe'] <= self.BUFFETT_CRITERIA["pe"]["threshold"],
                    "low_debt": metrics['debt_to_equity'] <= self.BUFFETT_CRITERIA["debt_to_equity"]["threshold"],
                    "profitable": metrics['profit_margin'] >= self.BUFFETT_CRITERIA["profit_margin"]["threshold"],
                    "positive_momentum": is_positive_momentum
                }
                
                criteria_passed = sum(1 for v in buffett_criteria.values() if v)
                buffett_grade = (
                    "A+" if criteria_passed == 5 else
                    "A" if criteria_passed == 4 else
                    "B" if criteria_passed == 3 else "C"
                )
                
                # 計算因子評分
                factor_scores = self._calculate_factor_scores(metrics, momentum)
                
                # 計算最終評分
                final_score = self._calculate_buffett_score(
                    factor_scores,
                    criteria_passed,
                    is_positive_momentum,
                    market_phase
                )
                
                # 風險評估
                total_risk, risk_breakdown = self._calculate_risk_score(metrics, hist)
                
                # 投資建議
                recommendation = (
                    "強力推薦 ⭐⭐⭐" if final_score > 85 and criteria_passed >= 4 else
                    "優質標的 ⭐⭐" if final_score > 70 and criteria_passed >= 3 else
                    "價值觀察 ⭐" if final_score > 55 else "暫避鋒芒"
                )
                
                logger.info(f"✅ {self.symbol} ({self.sector}) 評分: {final_score:.1f}, 等級: {buffett_grade}")
                
                return {
                    "symbol": self.symbol,
                    "companyName": company_name,
                    "sector": self.sector,
                    "buffettScore": round(float(final_score), 1),
                    "currentPrice": round(float(current_price), 2),
                    "momentum": round(float(momentum['1y']), 2),
                    "totalRisk": round(float(total_risk), 1),
                    "roe": round(float(metrics['roe']), 2),
                    "pe": round(float(metrics['pe']), 2) if metrics['pe'] < 500 else "N/A",
                    "recommendation": recommendation,
                    "marketPhase": market_phase,
                    "factors": factor_scores,
                    "risks": risk_breakdown,
                    "buffettCriteria": {
                        "grade": buffett_grade,
                        "criteria_passed": criteria_passed,
                        "details": {
                            "high_roe": f"{'✅' if buffett_criteria['high_roe'] else '❌'} ROE {metrics['roe']:.1f}% {'≥' if buffett_criteria['high_roe'] else '<'} 15%",
                            "reasonable_pe": f"{'✅' if buffett_criteria['reasonable_pe'] else '❌'} P/E {'N/A' if metrics['pe'] > 500 else f'{metrics['pe']:.1f}'} {'≤' if buffett_criteria['reasonable_pe'] else '>'} 25",
                            "low_debt": f"{'✅' if buffett_criteria['low_debt'] else '❌'} 債務比 {metrics['debt_to_equity']:.2f} {'≤' if buffett_criteria['low_debt'] else '>'} 1.0",
                            "profitable": f"{'✅' if buffett_criteria['profitable'] else '❌'} 利潤率 {metrics['profit_margin']:.1f}% {'≥' if buffett_criteria['profitable'] else '<'} 10%",
                            "positive_momentum": f"{'✅' if buffett_criteria['positive_momentum'] else '❌'} 6個月趨勢 {'正向' if buffett_criteria['positive_momentum'] else '偏弱'}"
                        }
                    },
                    "details": {
                        "ma200": round(float(tech_indicators['ma200']), 2),
                        "profit_margin": round(float(metrics['profit_margin']), 2),
                        "debt_to_equity": round(float(metrics['debt_to_equity']), 2),
                        "momentum_6m": round(float(momentum['6m']), 2),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ {self.symbol} 分析失敗: {e}")
            return None

# ==================== API 端點 ====================

@app.get("/")
async def root():
    """API 根端點"""
    return {
        "service": config.API_TITLE,
        "version": config.API_VERSION,
        "description": config.API_DESCRIPTION,
        "sectors": list(STOCK_POOLS.keys()),
        "total_stocks": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
        "endpoints": {
            "all_sectors": "/api/stock-pool",
            "specific_sector": "/api/stock-pool?sector=科技股",
            "top_25": "/api/top-25",
            "analyze_symbol": "/api/analyze?symbol=AAPL",
            "health": "/health"
        }
    }

@app.get("/api/stock-pool", response_model=List[SectorAnalysis])
async def get_stock_pool(
    sector: Optional[str] = Query(None, description="產業分類"),
    limit: int = Query(10, ge=1, le=50, description="每個產業返回的股票數量")
):
    """獲取股票池分析"""
    sectors_to_analyze = (
        [sector] if sector and sector in STOCK_POOLS 
        else list(STOCK_POOLS.keys())
    )
    
    results = []
    
    for sector_name in sectors_to_analyze:
        pool = STOCK_POOLS[sector_name]
        symbols = pool["symbols"]
        
        logger.info(f"📊 分析 {sector_name}: {len(symbols)} 支股票")
        
        # 並行分析
        tasks = [
            BuffettStockPicker(symbol, sector_name).analyze() 
            for symbol in symbols
        ]
        sector_results = [r for r in await asyncio.gather(*tasks) if r]
        
        # 排序並取前 N 名
        sector_results.sort(key=lambda x: x['buffettScore'], reverse=True)
        top_stocks = sector_results[:limit]
        
        # 統計
        avg_score = (
            sum(s['buffettScore'] for s in sector_results) / len(sector_results) 
            if sector_results else 0
        )
        avg_risk = (
            sum(s['totalRisk'] for s in sector_results) / len(sector_results) 
            if sector_results else 0
        )
        
        sector_risk = (
            "低風險" if avg_risk < 35 else 
            "中風險" if avg_risk < 55 else "高風險"
        )
        
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
    """巴菲特 TOP 25 股票池"""
    logger.info("🎯 篩選 TOP 25 股票池...")
    
    # 並行分析所有股票
    tasks = []
    for sector_name, pool in STOCK_POOLS.items():
        for symbol in pool["symbols"]:
            picker = BuffettStockPicker(symbol, sector_name)
            tasks.append(picker.analyze())
    
    logger.info(f"🚀 並行分析 {len(tasks)} 支股票...")
    results = await asyncio.gather(*tasks)
    
    # 過濾並排序
    all_stocks = [r for r in results if r]
    all_stocks.sort(key=lambda x: x.get('buffettScore', 0), reverse=True)
    
    top_25 = all_stocks[:25]
    
    if not top_25:
        return {
            "status": "success",
            "top_25_stocks": [],
            "statistics": {
                "average_score": 0,
                "average_risk": 0,
                "high_grade_stocks": 0,
                "sector_distribution": {}
            }
        }
    
    # 統計計算
    sectors_count = {}
    total_score = 0
    total_risk = 0
    high_grade_count = 0
    
    for stock in top_25:
        sector = stock.get('sector', '未知')
        sectors_count[sector] = sectors_count.get(sector, 0) + 1
        total_score += stock.get('buffettScore', 0)
        total_risk += stock.get('totalRisk', 0)
        
        criteria = stock.get('buffettCriteria', {})
        if criteria.get('grade') in ['A+', 'A']:
            high_grade_count += 1
    
    count = len(top_25)
    
    return {
        "status": "success",
        "title": "巴菲特 TOP 25 股票池",
        "description": "基於價值投資原則篩選的優質股票",
        "total_analyzed": len(all_stocks),
        "top_25_stocks": top_25,
        "statistics": {
            "average_score": round(total_score / count, 1),
            "average_risk": round(total_risk / count, 1),
            "high_grade_stocks": high_grade_count,
            "sector_distribution": sectors_count,
            "count": count
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
    symbol = symbol.upper().strip()
    
    if sector not in STOCK_POOLS:
        raise HTTPException(
            status_code=400,
            detail=f"無效的產業分類。可用選項: {list(STOCK_POOLS.keys())}"
        )
    
    logger.info(f"🔍 分析: {symbol} ({sector})")
    
    try:
        picker = BuffettStockPicker(symbol, sector)
        result = await picker.analyze()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"無法獲取 {symbol} 的數據。請確認代號是否正確。"
            )
        
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 分析 {symbol} 失敗: {e}")
        raise HTTPException(status_code=500, detail=f"伺服器錯誤: {str(e)}")

@app.get("/health")
async def health_check():
    """健康檢查"""
    uptime_seconds = int(time.time() - START_TIME)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    return {
        "status": "healthy",
        "version": config.API_VERSION,
        "timestamp": datetime.now().isoformat(),
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_seconds,
        "data_info": {
            "sectors_count": len(STOCK_POOLS),
            "total_stocks": sum(len(p["symbols"]) for p in STOCK_POOLS.values()),
            "sectors": list(STOCK_POOLS.keys())
        },
        "configuration": {
            "cache_expire_seconds": config.CACHE_EXPIRE_SECONDS,
            "max_concurrent_requests": config.MAX_CONCURRENT_REQUESTS,
            "max_requests_per_minute": config.MAX_REQUESTS_PER_MINUTE
        },
        "environment": "Render" if "RENDER" in os.environ else "Local"
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全域例外處理器"""
    logger.error(f"未處理的例外: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "伺服器內部錯誤",
            "detail": str(exc) if os.environ.get("DEBUG") else "請稍後再試"
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
