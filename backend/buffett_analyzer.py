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
    
    # 巴菲特的核心標準定義
    BUFFETT_CRITERIA = {
        "roe": {
            "threshold": 15, 
            "label": "股東權益報酬率 (ROE)",
            "unit": "%",
            "operator": ">="
        },
        "pe": {
            "threshold": 25, 
            "label": "本益比 (P/E)",
            "unit": "",
            "operator": "<="
        },
        "debt_to_equity": {
            "threshold": 1.0, # 財報通常用比率，100% = 1.0
            "label": "債務權益比",
            "unit": "",
            "operator": "<="
        },
        "profit_margin": {
            "threshold": 10, 
            "label": "淨利率",
            "unit": "%",
            "operator": ">="
        },
        "consistent_earnings": {
            "required": True,
            "label": "獲利穩定度",
            "description": "過去 3-5 年連續盈利"
        },
        "moat": {
            "required": True,
            "label": "經濟護城河",
            "description": "品牌影響力或市場獨佔地位"
        }
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

            # ==================== 優化後的獲取數據 ====================
            try:
                # 1. 建議先檢查 ticker 是否有效
                # info 獲取非常緩慢且容易失敗，可以考慮使用 fast_info 作為備選
                info = self.stock.info
                
                # 2. 歷史數據抓取 
                # 加入 auto_adjust=True 確保股價經過還原（考慮除權息）
                hist = self.stock.history(period="1y", auto_adjust=True)
                
            except Exception as e:
                # 捕捉特定錯誤，避免因為某一隻股票崩潰導致整個併發任務失敗
                logger.error(f"❌ {self.symbol}: 數據獲取發生異常 - {str(e)}")
                return None
            
            # 3. 數據完整性檢查
            # 檢查 info 是否為空，或是否只是一個錯誤訊息字典
            if not info or len(info) < 5: 
                logger.warning(f"❌ {self.symbol}: 無法獲取公司基本面資料 (Info 為空)")
                return None
            
            if hist.empty or len(hist) < 20: # 寬鬆一點，有時新上市股票天數較少
                logger.warning(f"❌ {self.symbol}: 股價歷史數據不足")
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

            # ==================== 財務指標清洗與標準化 ====================
            
            # 1. ROE 處理 (yfinance 通常給 0.15 代表 15%)
            raw_roe = info.get('returnOnEquity')
            if raw_roe is not None:
                # 自動偵測：如果是 0.15 轉為 15；如果是 15 則維持 15
                roe = raw_roe * 100 if abs(raw_roe) < 1 else raw_roe
            else:
                roe = 0  # 缺失值設為 0，評分時會反映出數據不足
                
            # 2. P/E 處理 (本益比)
            # 優先順序：預估 P/E > 滾動 P/E
            pe = info.get('forwardPE') or info.get('trailingPE')
            if pe is None or pe <= 0:
                pe = 999  # 使用極大值而非 25，因為 P/E 越小越好，999 代表「極不推薦」
            else:
                pe = min(pe, 500)  # 限制上限，避免極端數值破壞圖表
                
            # 3. 淨利率 (Profit Margin)
            # yfinance 的 profitMargins 幾乎都是小數 (例如 0.2 = 20%)
            margin = info.get('profitMargins')
            profit_margin = (margin * 100) if margin is not None else 0
            
            # 4. 債務權益比 (Debt to Equity)
            # 注意：yfinance 有些回傳 100 代表 100%，有些回傳 1.0
            raw_d_e = info.get('debtToEquity')
            if raw_d_e is not None:
                debt_to_equity = raw_d_e if raw_d_e < 5 else raw_d_e / 100
            else:
                debt_to_equity = 2.0  # 缺失值預設為較高風險 (200%)
            
            # ==================== 市場分析與趨勢判斷 ====================
            
            # 1. 計算 MA200 (長期趨勢線)
            # 使用 min_periods=1 確保數據不足 200 天時也能計算出平均值，不至於報錯
            ma200_series = hist['Close'].rolling(window=200, min_periods=1).mean()
            ma200 = ma200_series.iloc[-1]
            
            # 2. 計算 MA50 (中期趨勢線，巴菲特也看重中期支撐)
            ma50 = hist['Close'].rolling(window=50, min_periods=1).mean().iloc[-1]
            
            # 3. 更精準的市場階段判斷 (Market Phase)
            # 對於單一股票，我們通常看它是處於「上升通道」還是「修正階段」
            if current_price > ma200:
                market_phase = "多頭排列" if current_price > ma50 else "高檔震盪"
            else:
                market_phase = "空頭趨勢" if current_price < ma50 else "低檔打底"
            
            # 4. 計算價格偏離度 (與 MA200 的距離)
            # 這是風險評估的重要指標：如果股價高於 MA200 太多，可能代表過熱
            price_deviation = ((current_price - ma200) / ma200) * 100
            
            # ==================== 動能與趨勢強度分析 ====================
            
            # 1. 一年動能 (Momentum 1Y)
            # 使用 try-except 確保數據量極少時不會 index out of bounds
            try:
                one_year_ago = hist['Close'].iloc[0]
                momentum_1y = ((current_price - one_year_ago) / one_year_ago) * 100
                
                # 2. 六個月動能 (Momentum 6M)
                # 使用 len(hist)//2 或是精確找 126 個交易日
                half_year_idx = len(hist) // 2
                six_months_ago = hist['Close'].iloc[half_year_idx]
                momentum_6m = ((current_price - six_months_ago) / six_months_ago) * 100
                
                # 3. 短期強勢 (1個月動能) - 巴菲特雖看長，但進場看短
                one_month_idx = max(0, len(hist) - 21)
                one_month_ago = hist['Close'].iloc[one_month_idx]
                momentum_1m = ((current_price - one_month_ago) / one_month_ago) * 100
                
            except Exception as e:
                logger.warning(f"⚠️ {self.symbol} 動能計算失敗: {e}")
                momentum_1y, momentum_6m, momentum_1m = 0, 0, 0

            # 4. 動能狀態判斷
            # 好的價值股應該是：長期低估 + 中短期動能轉強
            is_positive_momentum = momentum_6m > 0 and momentum_1m > -5

            # ==================== 1. 巴菲特標準檢查 (布林值) ====================
            buffett_criteria = {
                "high_roe": roe >= self.BUFFETT_CRITERIA["roe"]["threshold"],
                "reasonable_pe": 0 < pe <= self.BUFFETT_CRITERIA["pe"]["threshold"],
                # 注意：debt_to_equity 在清洗時已標準化，此處判斷應與閾值一致
                "low_debt": debt_to_equity <= (self.BUFFETT_CRITERIA["debt_to_equity"]["threshold"]),
                "profitable": profit_margin >= self.BUFFETT_CRITERIA["profit_margin"]["threshold"],
                "positive_momentum": is_positive_momentum
            }
            
            criteria_passed = sum(1 for v in buffett_criteria.values() if v)
            
            # 等級給予更嚴格的定義 (增加 S 級別或更細緻的劃分)
            buffett_grade = "A+" if criteria_passed == 5 else "A" if criteria_passed == 4 else "B" if criteria_passed == 3 else "C"

            # ==================== 2. 四大因子深度評分 (0-100) ====================
            
            # V (Value) 價值評分：本益比越低分越高，但虧損(999)則給 0 分
            if pe == 999 or pe <= 0:
                v_score = 0
            else:
                v_score = 100 if pe < 12 else 80 if pe < 20 else 50 if pe < 30 else 20
            
            # Q (Quality) 品質評分：基於 ROE，巴菲特最愛 20% 以上的公司
            # 使用更平滑的公式：ROE 25% 拿滿分
            q_score = min(100, max(0, roe * 4))
            
            # M (Momentum) 動能評分：不只是看 1y，應該綜合 6m 和 1y
            # 加上 50 作為基準分，避免大跌股票出現負分
            m_score = max(0, min(100, (momentum_1y * 0.4 + momentum_6m * 0.6) + 50))
            
            # G (Growth) 成長評分：營收成長是護城河的體現
            # 預設給 60 分 (合格線)，表現優異者加分
            rev_growth = info.get('revenueGrowth', 0) * 100
            g_score = min(100, max(0, rev_growth * 2 + 50)) if rev_growth != 0 else 60

            # ==================== 3. 最終巴菲特總分計算 ====================
            # 權重分配：品質 (ROE) 40%, 價值 (PE) 30%, 成長 20%, 動能 10%
            # 這最符合巴菲特「以合理價格買入卓越公司」的理念
            buffett_score = (q_score * 0.4) + (v_score * 0.3) + (g_score * 0.2) + (m_score * 0.1)
            
            # ==================== 1. 產業加權（巴菲特偏好） ====================
            sector_weights = {
                "金融股": {"quality": 1.15, "value": 1.1},   # 強調穩健與估值
                "民生消費股": {"quality": 1.1, "value": 1.05},
                "科技股": {"growth": 1.15, "momentum": 1.05} # 強調成長與動能
            }
            
            weight = sector_weights.get(self.sector, {})
            # 乘完加權後，使用 min(100, ...) 確保單項分數不會爆表
            v_score = min(100, v_score * weight.get("value", 1.0))
            q_score = min(100, q_score * weight.get("quality", 1.0))
            m_score = min(100, m_score * weight.get("momentum", 1.0))
            g_score = min(100, g_score * weight.get("growth", 1.0))

            # ==================== 2. 綜合評分計算 ====================
            buffett_score = (
                v_score * 0.35 + 
                q_score * 0.35 + 
                m_score * 0.15 + 
                g_score * 0.15
            )
            
            # 標準加成：如果有通過巴菲特標準，給予獎勵分
            if criteria_passed >= 4:
                buffett_score *= 1.15 # 獎勵 15%
            elif criteria_passed >= 3:
                buffett_score *= 1.05 # 獎勵 5%

            # ==================== 3. 趨勢懲罰與最終分數 ====================
            final_score = buffett_score
            # 如果動能為負，或者處於空頭趨勢，進行折價（巴菲特不接落下的刀子）
            if not is_positive_momentum:
                final_score *= 0.75 
            if market_phase == "空頭趨勢":
                final_score *= 0.85
            
            # 確保最終總分在 0-100 之間
            final_score = max(0, min(100, final_score))

            # ==================== 4. 風險評估 (Risk Score) ====================
            # 債務風險：若 debt_to_equity 為 1.5 代表 150%
            debt_r = min(100, (debt_to_equity * 50)) if debt_to_equity else 30
            
            # 估值風險：PE 越高風險越高，若 PE=999(虧損) 則風險 100
            val_r = 100 if pe >= 100 else (pe / 40) * 100
            
            # 波動風險 (Volatility)：
            returns = hist['Close'].pct_change().dropna()
            if len(returns) > 20:
                # 年化波動度
                vol_r = returns.std() * np.sqrt(252) * 100 
            else:
                vol_r = 50 # 數據不足給予中等風險
            
            # 綜合風險 (0-100)：越低越安全
            total_risk = min(100, (debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2))

            # ==================== 5. 投資建議系統 ====================
            # 結合分數與通過的標準數量
            if final_score > 85 and criteria_passed >= 4:
                recommendation = "強力推薦 ⭐⭐⭐"
            elif final_score > 70 and criteria_passed >= 3:
                recommendation = "優質標的 ⭐⭐"
            elif final_score > 55:
                recommendation = "價值觀察 ⭐"
            else:
                recommendation = "暫避鋒芒"

            # 確保使用我們最終計算的評分
            display_score = round(float(final_score), 1)

            # 記錄 Log
            logger.info(f"✅ {self.symbol} ({self.sector}) 評分: {display_score}, 等級: {buffett_grade}")

            return {
                "symbol": self.symbol,
                "companyName": company_name if 'company_name' in locals() else self.symbol,
                "sector": self.sector,
                "buffettScore": display_score,
                "currentPrice": round(float(current_price), 2),
                "momentum": round(float(momentum_1y), 2),
                "totalRisk": round(float(total_risk), 1),
                "roe": round(float(roe), 2), # 使用清洗後的 roe
                "pe": round(float(pe), 2) if pe < 500 else "N/A", # 若虧損顯示 N/A
                "recommendation": recommendation,
                "marketPhase": market_phase,
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
                "buffettCriteria": {
                    "grade": buffett_grade,
                    "criteria_passed": criteria_passed,
                    "details": {
                        "high_roe": f"{'✅' if buffett_criteria['high_roe'] else '❌'} ROE {roe:.1f}% {'≥' if buffett_criteria['high_roe'] else '<'} 15%",
                        "reasonable_pe": f"{'✅' if buffett_criteria['reasonable_pe'] else '❌'} P/E {'N/A' if pe > 500 else f'{pe:.1f}'} {'≤' if buffett_criteria['reasonable_pe'] else '>' if pe < 500 else '(虧損)'} 25",
                        "low_debt": f"{'✅' if buffett_criteria['low_debt'] else '❌'} 債務比 {debt_to_equity:.1f}% {'≤' if buffett_criteria['low_debt'] else '>'} 1.0",
                        "profitable": f"{'✅' if buffett_criteria['profitable'] else '❌'} 利潤率 {profit_margin:.1f}% {'≥' if buffett_criteria['profitable'] else '<'} 10%",
                        "positive_momentum": f"{'✅' if buffett_criteria['positive_momentum'] else '❌'} 6個月趨勢 {'正向' if buffett_criteria['positive_momentum'] else '偏弱'}"
                    }
                },
                "details": {
                    "ma200": round(float(ma200), 2),
                    "profit_margin": round(float(profit_margin), 2),
                    "debt_to_equity": round(float(debt_to_equity), 2),
                    "momentum_6m": round(float(momentum_6m), 2),
                    "timestamp": datetime.now().isoformat()
                }
            }

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

import asyncio # 確保有 import

@app.get("/api/top-25")
async def get_top_25():
    """
    巴菲特的 25 支股票池
    從三大產業中選出評分最高的 25 支股票
    """
    
    logger.info("🎯 開始篩選巴菲特 TOP 25 股票池...")
    
    # ==================== 修改後的並行分析邏輯 ====================
    tasks = []
    
    # 1. 建立所有股票的分析任務，但不立即執行
    for sector_name, pool in STOCK_POOLS.items():
        logger.info(f"📅 已排程分析產業: {sector_name}")
        for symbol in pool["symbols"]:
            picker = BuffettStockPicker(symbol, sector_name)
            # 將協程物件加入清單
            tasks.append(picker.analyze())
    
    # 2. 同時啟動所有任務 (並行執行)
    logger.info(f"🚀 啟動並行分析，共 {len(tasks)} 隻股票...")
    
    # asyncio.gather 會同時發送請求，等待所有股票分析完畢
    results = await asyncio.gather(*tasks)
    
    # 3. 過濾掉分析失敗 (None) 的結果並存入 all_stocks
    all_stocks = [r for r in results if r is not None]
    
    logger.info(f"✅ 分析完成，成功獲取 {len(all_stocks)} 隻股票數據")
    # ============================================================
    
    # 1. 按評分排序 (確保 buffettScore 存在，若無則預設為 0)
    # 使用 .get() 可以防止某隻股票資料殘缺導致程式崩潰
    all_stocks.sort(key=lambda x: x.get('buffettScore', 0), reverse=True)
    
    # 2. 取前 25 名 (如果總數不足 25，這行程式碼也會自動處理，不會報錯)
    top_25 = all_stocks[:25]
    
    # 3. 檢查是否有資料 (預防性檢查)
    if not top_25:
        logger.warning("⚠️ 警告：沒有任何股票分析成功！")
        # 可以回傳一個空的成功回應，避免前端顯示 Error
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
    
    # 1. 取得實際取得的股票數量
    actual_count = len(top_25)
    
    # 2. 初始化統計變數
    sectors_count = {}
    total_score = 0
    total_risk = 0
    high_grade_count = 0
    
    # 3. 進行統計迴圈
    for stock in top_25:
        # 產業分布統計
        sector = stock.get('sector', '未知')
        sectors_count[sector] = sectors_count.get(sector, 0) + 1
        
        # 累加分數與風險 (使用 get 預防 Key 缺失)
        total_score += stock.get('buffettScore', 0)
        total_risk += stock.get('totalRisk', 0)
        
        # 判斷等級 (加入安全導航)
        criteria = stock.get('buffettCriteria', {})
        if criteria.get('grade') in ['A+', 'A']:
            high_grade_count += 1
            
    # 4. 計算平均值 (使用實際數量作為除數，避免除以零)
    divisor = actual_count if actual_count > 0 else 1
    
    return {
        "status": "success",  # 讓前端更容易判斷請求成功
        "title": "巴菲特 TOP 25 股票池",
        "description": "基於價值投資原則篩選的優質股票",
        "total_analyzed": len(all_stocks),
        "top_25_stocks": top_25,
        "statistics": {
            "average_score": round(total_score / divisor, 1),
            "average_risk": round(total_risk / divisor, 1),
            "high_grade_stocks": high_grade_count,
            "sector_distribution": sectors_count,
            "count": actual_count  # 回傳實際數量給前端參考
        },
        "criteria": getattr(BuffettStockPicker, 'BUFFETT_CRITERIA', {}),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/analyze")
async def analyze_single_stock(
    symbol: str = Query(..., description="股票代號，例如: AAPL"),
    sector: str = Query("科技股", description="產業分類")
):
    """
    單一股票即時分析
    """
    symbol = symbol.upper().strip()
    logger.info(f"🔍 正在進行單一股票深度分析: {symbol} (產業: {sector})")
    
    try:
        # 1. 初始化分析器
        picker = BuffettStockPicker(symbol, sector)
        
        # 2. 執行分析
        # 注意：如果你的分析器內部沒有處理異常，這裡可以用 try-except 包起來
        result = await picker.analyze()
        
        # 3. 檢查結果
        if not result:
            logger.warning(f"⚠️ {symbol} 分析結果為空，可能是代號錯誤或數據源(Yahoo Finance)無資料")
            raise HTTPException(
                status_code=404, 
                detail=f"無法獲取 {symbol} 的分析數據。請確認代號是否正確，或該公司是否缺少近期的財務報表。"
            )
        
        # 4. 回傳結果並加入成功狀態
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        logger.error(f"❌ 分析 {symbol} 時發生非預期錯誤: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"伺服器分析錯誤: {str(e)}"
        )

import time # 記得在文件上方 import time

# 在檔案頂部定義啟動時間
START_TIME = time.time()

@app.get("/health")
async def health_check():
    """
    系統健康檢查
    提供運行狀態、數據規模及伺服器效能資訊
    """
    # 計算運行秒數
    uptime_seconds = int(time.time() - START_TIME)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": f"{uptime_seconds} seconds",
        "data_info": {
            "sectors_count": len(STOCK_POOLS),
            "total_stocks_in_pool": sum(len(pool["symbols"]) for pool in STOCK_POOLS.values()),
            "monitored_sectors": list(STOCK_POOLS.keys())
        },
        "configuration": {
            "cache_expire_seconds": CACHE_EXPIRE_SECONDS,
            "timezone": "UTC"
        },
        "server_environment": "Render.com" if "RENDER" in os.environ else "local"
    }

if __name__ == "__main__":
    import uvicorn
    # 優先讀取 Render 提供的 PORT，若無則預設 10000
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
