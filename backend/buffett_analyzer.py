"""
Buffett Stock Picker - 巴菲特選股系統
完整後端代碼 - 修復所有 JSON 序列化問題
Version: 5.3
"""
import os
import logging
import random
import asyncio
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta, time as dt_time
from contextlib import asynccontextmanager
import json

import numpy as np
import pandas as pd
import requests_cache
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

# ==================== 配置管理 ====================

class Config:
    CACHE_PATH = "./yfinance_stock_cache"
    CACHE_EXPIRE_SECONDS = 86400
    DAILY_CACHE_PATH = "./daily_analysis_cache.json"
    MAX_REQUESTS_PER_MINUTE = 500
    MIN_REQUEST_DELAY = 0
    MIN_HISTORY_DAYS = 5
    MIN_INFO_FIELDS = 1
    MAX_CONCURRENT_REQUESTS = 30
    DAILY_UPDATE_HOUR = 0
    DAILY_UPDATE_MINUTE = 0
    API_TITLE = "Buffett Stock Picker API"
    API_VERSION = "5.3"
    API_DESCRIPTION = "巴菲特選股系統 - 完整修復版"

config = Config()

# ==================== 日誌配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== JSON 序列化助手 ====================

def safe_float(value, default=0.0):
    """安全轉換為有效的浮點數,自動處理 inf/NaN"""
    try:
        val = float(value)
        if np.isnan(val) or np.isinf(val):
            return default
        return val
    except (TypeError, ValueError):
        return default

def convert_to_serializable(obj):
    """將所有數據轉換為 JSON 可序列化格式,處理 inf/NaN"""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        val = float(obj)
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (bool, int, str)) or obj is None:
        return obj
    elif hasattr(obj, '__dict__'):
        return convert_to_serializable(obj.__dict__)
    else:
        return str(obj)

# ==================== 快取管理器 ====================

class DailyCacheManager:
    """管理每日分析結果的快取"""
    
    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self.cache_data = None
        self.last_update = None
        self.is_analyzing = False
        
    def load_cache(self) -> Optional[dict]:
        """載入快取資料"""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_data = data
                    self.last_update = datetime.fromisoformat(data.get('last_update', ''))
                    logger.info(f"✅ 載入快取成功 - 更新時間: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
                    return data
        except Exception as e:
            logger.error(f"❌ 載入快取失敗: {e}")
        return None
    
    def save_cache(self, data: dict):
        """儲存快取資料 - 確保所有數據都可序列化"""
        try:
            serializable_data = convert_to_serializable(data)
            
            cache_data = {
                'last_update': datetime.now().isoformat(),
                'data': serializable_data
            }
            
            cache_dir = os.path.dirname(self.cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            
            temp_path = self.cache_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            os.replace(temp_path, self.cache_path)
            
            self.cache_data = cache_data
            self.last_update = datetime.now()
            logger.info(f"✅ 快取已儲存: {self.cache_path}")
            
        except Exception as e:
            logger.error(f"❌ 儲存快取失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def is_cache_valid(self) -> bool:
        """檢查快取是否仍然有效"""
        if not self.last_update:
            return False
        now = datetime.now()
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

cache_manager = DailyCacheManager(config.DAILY_CACHE_PATH)

# ==================== 快取與啟動管理 ====================

session = requests_cache.CachedSession(
    config.CACHE_PATH,
    expire_after=config.CACHE_EXPIRE_SECONDS,
    backend='sqlite'
)

START_TIME = time.time()
background_task = None

# ==================== 股票池定義 ====================

STOCK_POOLS = {
    "科技股": {
        "description": "科技創新類股票",
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            "CRM", "ADBE", "ORCL", "SNOW", "PLTR",
            "INTC", "QCOM", "AVGO", "TSM", "ASML",
            "BABA", "SHOP", "SE"
        ]
    },
    "金融股": {
        "description": "銀行、保險與金融服務",
        "symbols": [
            "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC",
            "BRK-B", "AIG", "MET", "PRU", "AFL",
            "V", "MA", "PYPL", "SQ", "AXP",
            "BLK", "SCHW", "BX"
        ]
    },
    "民生消費股": {
        "description": "日常消費與零售",
        "symbols": [
            "WMT", "HD", "COST", "TGT", "LOW", "TJX",
            "KO", "PEP", "MDLZ", "GIS",
            "MCD", "SBUX", "YUM", "CMG",
            "PG", "UL", "CL", "KMB",
            "JNJ", "PFE", "UNH"
        ]
    }
}

# ==================== 速率限制器 ====================

class RateLimiter:
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

# ==================== 資料獲取優化 ====================

class DataFetcher:
    @staticmethod
    async def fetch_stock_data(symbol: str) -> Tuple[Optional[dict], Optional[pd.DataFrame]]:
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                stock = yf.Ticker(symbol)
                
                try:
                    info = stock.info
                except Exception:
                    info = stock.fast_info.__dict__ if hasattr(stock, 'fast_info') else {}
                
                hist = stock.history(period="1y", auto_adjust=True)
                
                if not info or len(info) < config.MIN_INFO_FIELDS:
                    return None, None
                
                if hist.empty or len(hist) < config.MIN_HISTORY_DAYS:
                    return None, None
                
                return info, hist
                
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    logger.error(f"❌ {symbol}: {e}")
                    return None, None
    
    @staticmethod
    def normalize_financial_metrics(info: dict) -> Dict[str, float]:
        raw_roe = info.get('returnOnEquity')
        roe = (raw_roe * 100 if raw_roe and abs(raw_roe) < 1 else raw_roe) if raw_roe else 0
        roe = safe_float(roe, 0.0)
        
        pe = info.get('forwardPE') or info.get('trailingPE')
        pe = min(pe, 500) if pe and pe > 0 else 999
        pe = safe_float(pe, 999.0)
        
        margin = info.get('profitMargins')
        profit_margin = (margin * 100) if margin else 0
        profit_margin = safe_float(profit_margin, 0.0)
        
        raw_d_e = info.get('debtToEquity')
        debt_to_equity = (raw_d_e if raw_d_e < 5 else raw_d_e / 100) if raw_d_e else 2.0
        debt_to_equity = safe_float(debt_to_equity, 2.0)
        
        rev_growth = (info.get('revenueGrowth', 0) or 0) * 100
        rev_growth = safe_float(rev_growth, 0.0)
        
        return {
            'roe': roe,
            'pe': pe,
            'profit_margin': profit_margin,
            'debt_to_equity': debt_to_equity,
            'revenue_growth': rev_growth
        }

# ==================== 巴菲特選股引擎 ====================

class BuffettStockPicker:
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
                return {'1y': 0.0, '6m': 0.0, '1m': 0.0}
            
            one_year_ago = safe_float(hist['Close'].iloc[0], current_price)
            momentum['1y'] = safe_float(((current_price - one_year_ago) / one_year_ago) * 100, 0.0)
            
            half_year_idx = max(0, len(hist) // 2)
            six_months_ago = safe_float(hist['Close'].iloc[half_year_idx], current_price)
            momentum['6m'] = safe_float(((current_price - six_months_ago) / six_months_ago) * 100, 0.0)
            
            one_month_idx = max(0, len(hist) - 21)
            one_month_ago = safe_float(hist['Close'].iloc[one_month_idx], current_price)
            momentum['1m'] = safe_float(((current_price - one_month_ago) / one_month_ago) * 100, 0.0)
            
            return momentum
            
        except Exception as e:
            return {'1y': 0.0, '6m': 0.0, '1m': 0.0}
    
    def _calculate_technical_indicators(self, hist: pd.DataFrame) -> Dict[str, float]:
        ma200 = safe_float(hist['Close'].rolling(window=200, min_periods=1).mean().iloc[-1], 0)
        ma50 = safe_float(hist['Close'].rolling(window=50, min_periods=1).mean().iloc[-1], 0)
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
            'value': int(round(safe_float(v_score, 0))),
            'quality': int(round(safe_float(q_score, 0))),
            'momentum': int(round(safe_float(m_score, 0))),
            'growth': int(round(safe_float(g_score, 0)))
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
        
        return safe_float(max(0, min(100, final_score)), 0)
    
    def _calculate_risk_score(self, metrics: dict, hist: pd.DataFrame) -> Tuple[float, Dict[str, float]]:
        debt_r = min(100, metrics['debt_to_equity'] * 50)
        debt_r = safe_float(debt_r, 50.0)
        
        pe = metrics['pe']
        val_r = 100 if pe >= 100 else (pe / 40) * 100
        val_r = safe_float(val_r, 50.0)
        
        returns = hist['Close'].pct_change().dropna()
        if len(returns) > 20:
            std_val = safe_float(returns.std(), 0)
            if std_val > 0:
                vol_r = std_val * np.sqrt(252) * 100
            else:
                vol_r = 50.0
        else:
            vol_r = 50.0
        
        vol_r = safe_float(vol_r, 50.0)
        
        total_risk = min(100, debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2)
        total_risk = safe_float(total_risk, 50.0)
        
        return total_risk, {
            'debt': safe_float(debt_r, 50),
            'valuation': safe_float(val_r, 50),
            'volatility': safe_float(vol_r, 50)
        }
    
    async def analyze(self) -> Optional[dict]:
        try:
            async with rate_limiter.semaphore:
                await rate_limiter.wait_if_needed()
                rate_limiter.record_request()
                
                info, hist = await self.data_fetcher.fetch_stock_data(self.symbol)
                
                if not info or hist is None:
                    return None
                
                company_name = info.get('longName') or info.get('shortName') or self.symbol
                current_price = (
                    info.get('currentPrice') or
                    info.get('regularMarketPrice') or
                    safe_float(hist['Close'].iloc[-1], 0)
                )
                
                if not current_price or current_price <= 0:
                    return None
                
                current_price = safe_float(current_price, 0)
                
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
                    "high_roe": bool(metrics['roe'] >= self.BUFFETT_CRITERIA["roe"]["threshold"]),
                    "reasonable_pe": bool(0 < metrics['pe'] <= self.BUFFETT_CRITERIA["pe"]["threshold"]),
                    "low_debt": bool(metrics['debt_to_equity'] <= self.BUFFETT_CRITERIA["debt_to_equity"]["threshold"]),
                    "profitable": bool(metrics['profit_margin'] >= self.BUFFETT_CRITERIA["profit_margin"]["threshold"]),
                    "positive_momentum": bool(is_positive_momentum)
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
                
                logger.info(f"✅ {self.symbol} ({self.sector}) 評分: {final_score:.1f}")
                
                result = {
                    "symbol": str(self.symbol),
                    "companyName": str(company_name),
                    "sector": str(self.sector),
                    "buffettScore": safe_float(final_score, 0),
                    "currentPrice": safe_float(current_price, 0),
                    "momentum": safe_float(momentum['1y'], 0),
                    "totalRisk": safe_float(total_risk, 50),
                    "roe": safe_float(metrics['roe'], 0),
                    "pe": safe_float(metrics['pe'], 999) if metrics['pe'] < 500 else "N/A",
                    "recommendation": str(recommendation),
                    "marketPhase": str(market_phase),
                    "factors": {k: int(v) for k, v in factor_scores.items()},
                    "risks": {k: safe_float(v, 50) for k, v in risk_breakdown.items()},
                    "buffettCriteria": {
                        "grade": str(buffett_grade),
                        "criteria_passed": int(criteria_passed),
                        "details": {k: bool(v) for k, v in buffett_criteria.items()}
                    },
                    "details": {
                        "ma200": safe_float(tech_indicators['ma200'], 0),
                        "profit_margin": safe_float(metrics['profit_margin'], 0),
                        "debt_to_equity": safe_float(metrics['debt_to_equity'], 2),
                        "momentum_6m": safe_float(momentum['6m'], 0),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                return convert_to_serializable(result)
                
        except Exception as e:
            logger.error(f"❌ {self.symbol} 分析失敗: {e}")
            return None

# ==================== 核心分析函數 ====================

async def perform_full_analysis() -> Optional[dict]:
    """執行完整的股票分析"""
    try:
        if cache_manager.is_analyzing:
            logger.info("⚠️ 已有分析任務在執行中")
            return None
            
        cache_manager.is_analyzing = True
        logger.info("🚀 開始完整分析...")

        tasks = []
        for sector_name, pool in STOCK_POOLS.items():
            for symbol in pool["symbols"]:
                picker = BuffettStockPicker(symbol, sector_name)
                tasks.append(picker.analyze())
        
        results = await asyncio.gather(*tasks)
        all_stocks = [r for r in results if r]
        logger.info(f"✅ 成功分析 {len(all_stocks)} 支股票")
        
        if not all_stocks:
            cache_manager.is_analyzing = False
            return None
        
        all_stocks.sort(key=lambda x: x.get('buffettScore', 0), reverse=True)
        top_25 = all_stocks[:25]
        
        sectors_count = {}
        total_score = 0.0
        total_risk = 0.0
        high_grade_count = 0
        
        for stock in top_25:
            sector = stock.get('sector', '未知')
            sectors_count[sector] = sectors_count.get(sector, 0) + 1
            total_score += safe_float(stock.get('buffettScore', 0), 0)
            total_risk += safe_float(stock.get('totalRisk', 0), 0)
            
            criteria = stock.get('buffettCriteria', {})
            if criteria.get('grade') in ['A+', 'A']:
                high_grade_count += 1
        
        count = len(top_25)
        
        sector_analysis = []
        for sector_name, pool in STOCK_POOLS.items():
            sector_stocks = [s for s in all_stocks if s['sector'] == sector_name]
            sector_stocks.sort(key=lambda x: x['buffettScore'], reverse=True)
            
            avg_score = (
                sum(safe_float(s['buffettScore'], 0) for s in sector_stocks) / len(sector_stocks)
                if sector_stocks else 0.0
            )
            avg_risk = (
                sum(safe_float(s['totalRisk'], 0) for s in sector_stocks) / len(sector_stocks)
                if sector_stocks else 0.0
            )
            
            sector_risk = (
                "低風險" if avg_risk < 35 else 
                "中風險" if avg_risk < 55 else "高風險"
            )
            
            sector_analysis.append({
                "sector": str(sector_name),
                "description": str(pool["description"]),
                "total_stocks": int(len(pool["symbols"])),
                "analyzed_stocks": int(len(sector_stocks)),
                "top_picks": sector_stocks[:10],
                "average_score": safe_float(avg_score, 0),
                "average_risk": safe_float(avg_risk, 0),
                "sector_risk": str(sector_risk)
            })
        
        cache_manager.is_analyzing = False
        
        return {
            "top_25": {
                "status": "success",
                "title": "巴菲特 TOP 25 股票池",
                "description": "基於價值投資原則篩選的優質股票",
                "total_analyzed": int(len(all_stocks)),
                "rankings": top_25,
                "statistics": {
                    "average_score": safe_float(total_score / count if count > 0 else 0, 0),
                    "average_risk": safe_float(total_risk / count if count > 0 else 0, 0),
                    "high_grade_stocks": int(high_grade_count),
                    "sector_distribution": {str(k): int(v) for k, v in sectors_count.items()},
                    "count": int(count)
                },
                "criteria": BuffettStockPicker.BUFFETT_CRITERIA,
                "last_update": datetime.now().isoformat()
            },
            "sectors": sector_analysis
        }
        
    except Exception as e:
        logger.error(f"❌ 完整分析失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        cache_manager.is_analyzing = False
        return None

# ==================== 每日更新任務 ====================

async def daily_update_task():
    """每日定時更新任務"""
    while True:
        try:
            now = datetime.now()
            next_update = datetime.combine(
                now.date(),
                dt_time(config.DAILY_UPDATE_HOUR, config.DAILY_UPDATE_MINUTE)
            )
            
            if now >= next_update:
                next_update += timedelta(days=1)
            
            wait_seconds = (next_update - now).total_seconds()
            logger.info(f"⏰ 下次更新時間: {next_update.strftime('%Y-%m-%d %H:%M:%S')}")
            
            await asyncio.sleep(wait_seconds)
            
            logger.info("🚀 開始每日自動分析...")
            result = await perform_full_analysis()
            
            if result:
                cache_manager.save_cache(result)
                logger.info("✅ 每日分析完成")
            else:
                logger.error("❌ 每日分析失敗")
                
        except Exception as e:
            logger.error(f"❌ 每日更新任務錯誤: {e}")
            await asyncio.sleep(3600)

# ==================== 應用啟動管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    global background_task
    
    logger.info("🚀 巴菲特選股系統啟動中...")
    
    cache_manager.load_cache()
    
    if not cache_manager.is_cache_valid():
        logger.info("⚠️ 快取無效,立即執行分析...")
        result = await perform_full_analysis()
        if result:
            cache_manager.save_cache(result)
            
            rankings = result['top_25'].get('rankings', [])
            print("\n" + "="*60)
            print(f"  🏆 巴菲特選股排行榜 TOP 15")
            print("="*60)
            print(f"{'排名':<4} {'代號':<8} {'公司名稱':<25} {'評分':<6} {'等級':<4}")
            print("-"*60)
            
            for i, stock in enumerate(rankings[:15], 1):
                score = safe_float(stock.get('buffettScore', 0), 0)
                grade = stock.get('buffettCriteria', {}).get('grade', 'N/A')
                symbol = stock.get('symbol', 'N/A')
                name = stock.get('companyName', 'N/A')[:23]
                marker = "⭐" if score > 85 else "  "
                print(f"{i:<4} {symbol:<8} {name:<25} {score:<6.1f} {grade:<4} {marker}")
            
            print("-"*60)
            stats = result['top_25'].get('statistics', {})
            print(f"📊 總分析: {stats.get('count', 0)} 支 | 優質(A級+): {stats.get('high_grade_stocks', 0)} 支")
            print("="*60 + "\n")
    
    background_task = asyncio.create_task(daily_update_task())
    logger.info("✅ 系統啟動完成")
    
    yield
    
    if background_task:
        background_task.cancel()
    logger.info("👋 系統關閉")

# ==================== FastAPI 初始化 ====================

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ==================== API 端點 ====================

@app.get("/")
async def root():
    """API 根端點"""
    return {
        "service": config.API_TITLE,
        "version": config.API_VERSION,
        "status": "running",
        "cache_status": {
            "is_valid": cache_manager.is_cache_valid(),
            "last_update": cache_manager.last_update.isoformat() if cache_manager.last_update else None,
            "is_analyzing": cache_manager.is_analyzing
        },
        "total_stocks": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
        "endpoints": {
            "top_25": "/sp500-analysis",
            "sectors": "/api/stock-pool",
            "refresh": "/api/refresh (POST)",
            "health": "/health"
        }
    }

@app.get("/sp500-analysis")
async def get_sp500_analysis():
    """獲取 TOP 25 分析結果"""
    cached_data = cache_manager.get_cached_data()
    
    if cached_data and 'top_25' in cached_data:
        logger.info("✅ 返回快取的 TOP 25 數據")
        return cached_data['top_25']
    
    if cache_manager.is_analyzing:
        raise HTTPException(
            status_code=202,
            detail="正在分析中,請稍後再試 (約需 1-2 分鐘)"
        )
    
    logger.info("⚠️ 快取無效,立即啟動分析...")
    asyncio.create_task(async_analyze_and_cache())
    
    raise HTTPException(
        status_code=202,
        detail="分析任務已啟動,請在 1-2 分鐘後重試"
    )

@app.get("/api/stock-pool")
async def get_stock_pool(
    sector: Optional[str] = Query(None, description="產業分類"),
    limit: int = Query(10, ge=1, le=50, description="返回數量")
):
    """獲取產業分類數據"""
    cached_data = cache_manager.get_cached_data()
    
    if not cached_data or 'sectors' not in cached_data:
        if cache_manager.is_analyzing:
            raise HTTPException(status_code=202, detail="正在分析中")
        
        asyncio.create_task(async_analyze_and_cache())
        raise HTTPException(status_code=202, detail="分析任務已啟動")
    
    sectors_data = cached_data['sectors']
    
    if sector:
        sector_result = [s for s in sectors_data if s['sector'] == sector]
        if not sector_result:
            raise HTTPException(status_code=404, detail=f"找不到產業: {sector}")
        result = sector_result[0].copy()
        result['top_picks'] = result['top_picks'][:limit]
        return [result]
    
    results = []
    for s in sectors_data:
        s_copy = s.copy()
        s_copy['top_picks'] = s['top_picks'][:limit]
        results.append(s_copy)
    
    return results

@app.post("/api/refresh")
async def force_refresh(background_tasks: BackgroundTasks):
    """強制重新分析"""
    if cache_manager.is_analyzing:
        return {
            "status": "already_running",
            "message": "已有分析任務在執行中"
        }
    
    background_tasks.add_task(async_analyze_and_cache)
    
    return {
        "status": "accepted",
        "message": "分析任務已啟動",
        "estimated_time": "1-2 分鐘"
    }

@app.get("/health")
async def health_check():
    """健康檢查"""
    uptime_seconds = int(time.time() - START_TIME)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    return {
        "status": "healthy",
        "version": config.API_VERSION,
        "uptime": f"{hours}h {minutes}m",
        "cache_valid": cache_manager.is_cache_valid(),
        "is_analyzing": cache_manager.is_analyzing,
        "last_update": cache_manager.last_update.isoformat() if cache_manager.last_update else None
    }

async def async_analyze_and_cache():
    """背景分析並快取"""
    result = await perform_full_analysis()
    if result:
        cache_manager.save_cache(result)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
