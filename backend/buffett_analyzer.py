import os
import logging
import random
import asyncio
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta, time as dt_time
from functools import lru_cache
from contextlib import asynccontextmanager
import json
from pathlib import Path

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
    
    # 每日分析結果儲存路徑
    DAILY_CACHE_PATH = "/tmp/daily_analysis_cache.json"
    
    # 速率限制
    MAX_REQUESTS_PER_MINUTE = 20
    MIN_REQUEST_DELAY = 0.2
    
    # 資料要求
    MIN_HISTORY_DAYS = 20
    MIN_INFO_FIELDS = 5
    
    # 並行控制
    MAX_CONCURRENT_REQUESTS = 10
    
    # 每日更新時間 (UTC 時間,午夜 00:00)
    DAILY_UPDATE_HOUR = 0
    DAILY_UPDATE_MINUTE = 0
    
    # API 設定
    API_TITLE = "Buffett Stock Picker API"
    API_VERSION = "4.0"
    API_DESCRIPTION = "巴菲特選股系統 - 每日自動更新版"

config = Config()

# ==================== 日誌配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 每日快取管理器 ====================

class DailyCacheManager:
    """管理每日分析結果的快取"""
    
    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self.cache_data = None
        self.last_update = None
        
    def load_cache(self) -> Optional[dict]:
        """載入快取資料"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_data = data
                    self.last_update = datetime.fromisoformat(data.get('last_update', ''))
                    logger.info(f"✅ 載入快取成功,上次更新: {self.last_update}")
                    return data
        except Exception as e:
            logger.error(f"❌ 載入快取失敗: {e}")
        return None
    
    def save_cache(self, data: dict):
        """儲存快取資料"""
        try:
            cache_data = {
                'last_update': datetime.now().isoformat(),
                'data': data
            }
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.cache_data = cache_data
            self.last_update = datetime.now()
            logger.info(f"✅ 快取已儲存: {self.cache_path}")
            
        except Exception as e:
            logger.error(f"❌ 儲存快取失敗: {e}")
    
    def is_cache_valid(self) -> bool:
        """檢查快取是否仍然有效 (當日有效)"""
        if not self.last_update:
            return False
        
        now = datetime.now()
        # 如果是同一天的快取,視為有效
        return (
            self.last_update.date() == now.date() and
            self.cache_data is not None
        )
    
    def get_cached_data(self) -> Optional[dict]:
        """獲取快取資料"""
        if self.is_cache_valid():
            logger.info("✅ 使用快取資料")
            return self.cache_data.get('data')
        
        logger.info("⚠️ 快取已過期或不存在")
        return None

# 初始化快取管理器
cache_manager = DailyCacheManager(config.DAILY_CACHE_PATH)

# ==================== 快取與啟動管理 ====================

session = requests_cache.CachedSession(
    config.CACHE_PATH,
    expire_after=config.CACHE_EXPIRE_SECONDS,
    backend='sqlite'
)

START_TIME = time.time()

# 全域變數儲存背景任務
background_task = None

async def daily_update_task():
    """每日定時更新任務"""
    # 首次檢查是否需要初始分析
    if not cache_manager.is_cache_valid():
        logger.info("🔄 執行初始分析...")
        try:
            result = await perform_full_analysis()
            if result:
                cache_manager.save_cache(result)
                logger.info("✅ 初始分析完成")
        except Exception as e:
            logger.error(f"❌ 初始分析失敗: {e}")
    
    while True:
        try:
            now = datetime.now()
            
            # 計算下次更新時間 (今天或明天的指定時間)
            next_update = datetime.combine(
                now.date(),
                dt_time(config.DAILY_UPDATE_HOUR, config.DAILY_UPDATE_MINUTE)
            )
            
            # 如果今天的更新時間已過,改為明天
            if now >= next_update:
                next_update += timedelta(days=1)
            
            wait_seconds = (next_update - now).total_seconds()
            logger.info(f"⏰ 下次更新時間: {next_update.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_seconds/3600:.1f} 小時)")
            
            # 等待到下次更新時間
            await asyncio.sleep(wait_seconds)
            
            # 執行分析
            logger.info("🚀 開始每日自動分析...")
            result = await perform_full_analysis()
            
            if result:
                cache_manager.save_cache(result)
                logger.info("✅ 每日分析完成並已快取")
            else:
                logger.error("❌ 每日分析失敗")
                
        except Exception as e:
            logger.error(f"❌ 每日更新任務錯誤: {e}")
            # 發生錯誤時等待 1 小時後重試
            await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    global background_task
    
    logger.info("🚀 巴菲特選股系統啟動中...")
    
    # 載入現有快取
    cache_manager.load_cache()
    
    # 不在啟動時執行分析,避免 Render 健康檢查超時
    # 初始分析將在背景任務中處理
    if not cache_manager.is_cache_valid():
        logger.warning("⚠️ 快取無效,將在背景執行初始分析...")
    
    # 啟動背景更新任務
    background_task = asyncio.create_task(daily_update_task())
    logger.info("✅ 每日更新任務已啟動")
    
    yield
    
    # 關閉時取消背景任務
    if background_task:
        background_task.cancel()
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
    """改進的速率限制器"""
    
    def __init__(self):
        self.requests = []
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)
        
    def _clean_old_requests(self):
        now = datetime.now()
        self.requests = [
            req for req in self.requests 
            if now - req < timedelta(minutes=1)
        ]
    
    def can_make_request(self) -> bool:
        self._clean_old_requests()
        return len(self.requests) < config.MAX_REQUESTS_PER_MINUTE
    
    def record_request(self):
        self.requests.append(datetime.now())
    
    async def wait_if_needed(self):
        wait_count = 0
        while not self.can_make_request():
            wait_count += 1
            if wait_count == 1:
                logger.warning("⚠️ 達到速率限制,等待中...")
            await asyncio.sleep(3)
        await asyncio.sleep(random.uniform(0.1, config.MIN_REQUEST_DELAY))

rate_limiter = RateLimiter()

# ==================== 數據模型 ====================

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

# ==================== 資料獲取優化 ====================

class DataFetcher:
    """優化的資料獲取器"""
    
    @staticmethod
    async def fetch_stock_data(symbol: str) -> Tuple[Optional[dict], Optional[pd.DataFrame]]:
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(symbol, session=session)
                
                try:
                    info = stock.info
                except Exception:
                    logger.warning(f"⚠️ {symbol}: info 失敗,嘗試 fast_info")
                    info = stock.fast_info.__dict__ if hasattr(stock, 'fast_info') else {}
                
                hist = stock.history(period="1y", auto_adjust=True)
                
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
        raw_roe = info.get('returnOnEquity')
        roe = (raw_roe * 100 if raw_roe and abs(raw_roe) < 1 else raw_roe) if raw_roe else 0
        
        pe = info.get('forwardPE') or info.get('trailingPE')
        pe = min(pe, 500) if pe and pe > 0 else 999
        
        margin = info.get('profitMargins')
        profit_margin = (margin * 100) if margin else 0
        
        raw_d_e = info.get('debtToEquity')
        debt_to_equity = (raw_d_e if raw_d_e < 5 else raw_d_e / 100) if raw_d_e else 2.0
        
        rev_growth = (info.get('revenueGrowth', 0) or 0) * 100
        
        return {
            'roe': roe,
            'pe': pe,
            'profit_margin': profit_margin,
            'debt_to_equity': debt_to_equity,
            'revenue_growth': rev_growth
        }

# ==================== 巴菲特選股引擎 ====================

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
        try:
            momentum = {}
            
            if len(hist) < 21:
                return {'1y': 0, '6m': 0, '1m': 0}
            
            one_year_ago = hist['Close'].iloc[0]
            momentum['1y'] = ((current_price - one_year_ago) / one_year_ago) * 100
            
            half_year_idx = max(0, len(hist) // 2)
            six_months_ago = hist['Close'].iloc[half_year_idx]
            momentum['6m'] = ((current_price - six_months_ago) / six_months_ago) * 100
            
            one_month_idx = max(0, len(hist) - 21)
            one_month_ago = hist['Close'].iloc[one_month_idx]
            momentum['1m'] = ((current_price - one_month_ago) / one_month_ago) * 100
            
            return momentum
            
        except Exception as e:
            logger.warning(f"⚠️ {self.symbol} 動能計算失敗: {e}")
            return {'1y': 0, '6m': 0, '1m': 0}
    
    def _calculate_technical_indicators(self, hist: pd.DataFrame) -> Dict[str, float]:
        ma200 = hist['Close'].rolling(window=200, min_periods=1).mean().iloc[-1]
        ma50 = hist['Close'].rolling(window=50, min_periods=1).mean().iloc[-1]
        
        return {'ma200': ma200, 'ma50': ma50}
    
    def _assess_market_phase(self, current_price: float, ma200: float, ma50: float) -> str:
        if current_price > ma200:
            return "多頭排列" if current_price > ma50 else "高檔震盪"
        else:
            return "空頭趨勢" if current_price < ma50 else "低檔打底"
    
    def _calculate_factor_scores(self, metrics: dict, momentum: dict) -> Dict[str, int]:
        pe = metrics['pe']
        roe = metrics['roe']
        rev_growth = metrics['revenue_growth']
        
        v_score = 0 if pe >= 999 else (
            100 if pe < 12 else 80 if pe < 20 else 50 if pe < 30 else 20
        )
        
        q_score = min(100, max(0, roe * 4))
        m_score = max(0, min(100, (momentum['1y'] * 0.4 + momentum['6m'] * 0.6) + 50))
        g_score = min(100, max(0, rev_growth * 2 + 50)) if rev_growth != 0 else 60
        
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
        base_score = (
            factor_scores['value'] * 0.35 +
            factor_scores['quality'] * 0.35 +
            factor_scores['momentum'] * 0.15 +
            factor_scores['growth'] * 0.15
        )
        
        if criteria_passed >= 4:
            base_score *= 1.15
        elif criteria_passed >= 3:
            base_score *= 1.05
        
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
        debt_r = min(100, metrics['debt_to_equity'] * 50)
        
        pe = metrics['pe']
        val_r = 100 if pe >= 100 else (pe / 40) * 100
        
        returns = hist['Close'].pct_change().dropna()
        vol_r = (returns.std() * np.sqrt(252) * 100) if len(returns) > 20 else 50
        
        total_risk = min(100, debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2)
        
        return total_risk, {
            'debt': round(debt_r, 1),
            'valuation': round(val_r, 1),
            'volatility': round(vol_r, 1)
        }
    
    async def analyze(self) -> Optional[dict]:
        try:
            async with rate_limiter.semaphore:
                is_cached = session.cache.has_url(
                    f"https://query2.finance.yahoo.com/v8/finance/chart/{self.symbol}"
                )
                
                if not is_cached:
                    await rate_limiter.wait_if_needed()
                    rate_limiter.record_request()
                
                info, hist = await self.data_fetcher.fetch_stock_data(self.symbol)
                
                if not info or hist is None:
                    return None
                
                company_name = info.get('longName') or info.get('shortName') or self.symbol
                current_price = (
                    info.get('currentPrice') or
                    info.get('regularMarketPrice') or
                    hist['Close'].iloc[-1]
                )
                
                if not current_price or current_price <= 0:
                    return None
                
                metrics = self.data_fetcher.normalize_financial_metrics(info)
                momentum = self._calculate_momentum(hist, current_price)
                tech_indicators = self._calculate_technical_indicators(hist)
                market_phase = self._assess_market_phase(
                    current_price, 
                    tech_indicators['ma200'], 
                    tech_indicators['ma50']
                )
                
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
                
                factor_scores = self._calculate_factor_scores(metrics, momentum)
                final_score = self._calculate_buffett_score(
                    factor_scores,
                    criteria_passed,
                    is_positive_momentum,
                    market_phase
                )
                
                total_risk, risk_breakdown = self._calculate_risk_score(metrics, hist)
                
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

# ==================== 核心分析函數 ====================

async def perform_full_analysis() -> Optional[dict]:
    """執行完整的股票分析 (TOP 25 + 產業分類)"""
    try:
        logger.info("🚀 開始完整分析...")
        
        # 並行分析所有股票
        tasks = []
        for sector_name, pool in STOCK_POOLS.items():
            for symbol in pool["symbols"]:
                picker = BuffettStockPicker(symbol, sector_name)
                tasks.append(picker.analyze())
        
        logger.info(f"📊 並行分析 {len(tasks)} 支股票...")
        results = await asyncio.gather(*tasks)
        
        all_stocks = [r for r in results if r]
        logger.info(f"✅ 成功分析 {len(all_stocks)} 支股票")
        
        # 排序取 TOP 25
        all_stocks.sort(key=lambda x: x.get('buffettScore', 0), reverse=True)
        top_25 = all_stocks[:25]
        
        # 計算統計數據
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
        
        # 產業分類數據
        sector_analysis = []
        for sector_name, pool in STOCK_POOLS.items():
            sector_stocks = [s for s in all_stocks if s['sector'] == sector_name]
            sector_stocks.sort(key=lambda x: x['buffettScore'], reverse=True)
            
            avg_score = (
                sum(s['buffettScore'] for s in sector_stocks) / len(sector_stocks)
                if sector_stocks else 0
            )
            avg_risk = (
                sum(s['totalRisk'] for s in sector_stocks) / len(sector_stocks)
                if sector_stocks else 0
            )
            
            sector_risk = (
                "低風險" if avg_risk < 35 else 
                "中風險" if avg_risk < 55 else "高風險"
            )
            
            sector_analysis.append({
                "sector": sector_name,
                "description": pool["description"],
                "total_stocks": len(pool["symbols"]),
                "analyzed_stocks": len(sector_stocks),
                "top_picks": sector_stocks[:10],
                "average_score": round(avg_score, 1),
                "average_risk": round(avg_risk, 1),
                "sector_risk": sector_risk
            })
        
        return {
            "top_25": {
                "status": "success",
                "title": "巴菲特 TOP 25 股票池",
                "description": "基於價值投資原則篩選的優質股票",
                "total_analyzed": len(all_stocks),
                "rankings": top_25,
                "statistics": {
                    "average_score": round(total_score / count, 1) if count > 0 else 0,
                    "average_risk": round(total_risk / count, 1) if count > 0 else 0,
                    "high_grade_stocks": high_grade_count,
                    "sector_distribution": sectors_count,
                    "count": count
                },
                "criteria": BuffettStockPicker.BUFFETT_CRITERIA,
                "last_update": datetime.now().isoformat()
            },
            "sectors": sector_analysis
        }
        
    except Exception as e:
        logger.error(f"❌ 完整分析失敗: {e}")
        return None

# ==================== API 端點 ====================

@app.get("/")
async def root():
    """API 根端點"""
    return {
        "service": config.API_TITLE,
        "version": config.API_VERSION,
        "description": config.API_DESCRIPTION,
        "cache_status": {
            "is_valid": cache_manager.is_cache_valid(),
            "last_update": cache_manager.last_update.isoformat() if cache_manager.last_update else None
        },
        "sectors": list(STOCK_POOLS.keys()),
        "total_stocks": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
        "endpoints": {
            "sp500_analysis": "/sp500-analysis (主要端點 - 返回 TOP 25)",
            "stock_pool": "/api/stock-pool (產業分類)",
            "force_refresh": "/api/refresh (強制重新分析)",
            "health": "/health"
        }
    }

@app.get("/sp500-analysis")
async def get_sp500_analysis():
    """
    獲取 TOP 25 分析結果 (使用每日快取)
    前端主要調用此端點
    """
    # 嘗試從快取獲取
    cached_data = cache_manager.get_cached_data()
    
    if cached_data and 'top_25' in cached_data:
        logger.info("✅ 返回快取的 TOP 25 數據")
        return cached_data['top_25']
    
    # 快取無效,返回錯誤訊息
    logger.warning("⚠️ 快取無效,需要等待每日更新")
    raise HTTPException(
        status_code=503,
        detail="分析數據正在更新中,請稍後再試 (每日自動更新時間: UTC 00:00)"
    )

@app.get("/api/stock-pool")
async def get_stock_pool(
    sector: Optional[str] = Query(None, description="產業分類"),
    limit: int = Query(10, ge=1, le=50, description="每個產業返回的股票數量")
):
    """
    獲取產業分類數據 (使用每日快取)
    """
    cached_data = cache_manager.get_cached_data()
    
    if not cached_data or 'sectors' not in cached_data:
        raise HTTPException(
            status_code=503,
            detail="分析數據正在更新中,請稍後再試"
        )
    
    sectors_data = cached_data['sectors']
    
    # 如果指定產業,只返回該產業
    if sector:
        sector_result = [s for s in sectors_data if s['sector'] == sector]
        if not sector_result:
            raise HTTPException(
                status_code=404,
                detail=f"找不到產業: {sector}"
            )
        # 調整返回的股票數量
        result = sector_result[0].copy()
        result['top_picks'] = result['top_picks'][:limit]
        return [result]
    
    # 返回所有產業,調整每個產業的股票數量
    results = []
    for s in sectors_data:
        s_copy = s.copy()
        s_copy['top_picks'] = s['top_picks'][:limit]
        results.append(s_copy)
    
    return results

@app.post("/api/refresh")
async def force_refresh(background_tasks: BackgroundTasks):
    """
    強制重新分析 (管理員功能)
    分析將在背景執行
    """
    async def refresh_task():
        logger.info("🔄 強制重新分析...")
        result = await perform_full_analysis()
        if result:
            cache_manager.save_cache(result)
            logger.info("✅ 強制分析完成")
    
    background_tasks.add_task(refresh_task)
    
    return {
        "status": "accepted",
        "message": "分析任務已啟動,將在背景執行",
        "estimated_time": "1-2 分鐘"
    }

@app.get("/health")
async def health_check():
    """健康檢查"""
    uptime_seconds = int(time.time() - START_TIME)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    cache_valid = cache_manager.is_cache_valid()
    
    return {
        "status": "healthy",
        "version": config.API_VERSION,
        "timestamp": datetime.now().isoformat(),
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_seconds,
        "cache_status": {
            "is_valid": cache_valid,
            "last_update": cache_manager.last_update.isoformat() if cache_manager.last_update else None,
            "next_update": "每日 UTC 00:00"
        },
        "data_info": {
            "sectors_count": len(STOCK_POOLS),
            "total_stocks": sum(len(p["symbols"]) for p in STOCK_POOLS.values()),
            "sectors": list(STOCK_POOLS.keys())
        },
        "configuration": {
            "cache_expire_seconds": config.CACHE_EXPIRE_SECONDS,
            "max_concurrent_requests": config.MAX_CONCURRENT_REQUESTS,
            "daily_update_time": f"{config.DAILY_UPDATE_HOUR:02d}:{config.DAILY_UPDATE_MINUTE:02d} UTC"
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
