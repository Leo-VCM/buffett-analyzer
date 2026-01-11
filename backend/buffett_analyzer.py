import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

class BuffettStyleAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.today = datetime.now().date()
        
    def calculate_momentum(self, hist):
        """計算 12 個月價格回報動能"""
        try:
            if len(hist) < 252: return 0
            current_price = hist['Close'].iloc[-1]
            price_1y_ago = hist['Close'].iloc[-252]
            momentum = ((current_price - price_1y_ago) / price_1y_ago) * 100
            return round(float(momentum), 2)
        except:
            return 0
    
    def analyze(self):
        """執行完整的多因子與風險分析"""
        try:
            stock = yf.Ticker(self.symbol)
            info = stock.info
            hist = stock.history(period='1y')
            
            if hist.empty or len(hist) < 20:
                return None

            # --- A. 基礎數據提取 ---
            current_price = info.get('currentPrice', 0)
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            pb = info.get('priceToBook', 0) or 0
            # ROE 處理 (百分比化)
            roe_raw = info.get('returnOnEquity', 0) or 0
            roe = roe_raw * 100 if abs(roe_raw) < 1.0 else roe_raw
            
            debt_to_equity = info.get('debtToEquity', 0) or 0
            profit_margin = (info.get('profitMargins', 0) or 0) * 100
            revenue_growth = (info.get('revenueGrowth', 0) or 0) * 100
            
            # 年化波動率
            volatility = float(hist['Close'].pct_change().std() * np.sqrt(252) * 100) if len(hist) > 10 else 0

            # --- B. 多因子評分 (Factors) ---
            # 1. 價值 (Value): PE < 15 為滿分
            f_value = 100 if 0 < pe < 15 else max(0, 100 - (pe - 15) * 3) if pe > 0 else 0
            # 2. 質量 (Quality): ROE > 20% 為滿分
            f_quality = min(100, roe * 5) if roe > 0 else 0
            # 3. 動能 (Momentum): 股價回報
            momentum = self.calculate_momentum(hist)
            f_momentum = min(100, max(0, momentum))
            # 4. 成長 (Growth): 營收成長
            f_growth = min(100, max(0, revenue_growth))

            # 計算巴菲特總分 (權重配比)
            buffettScore = round((f_value * 0.35) + (f_quality * 0.35) + (f_momentum * 0.2) + (f_growth * 0.1), 2)

            # --- C. 風險評估 (Risks) ---
            # 數值越高代表風險越大 (0-100)
            r_debt = min(100, debt_to_equity) # 負債比越高風險越高
            r_valuation = 100 if pe > 50 else (pe * 2 if pe > 0 else 100) # 貴不貴
            r_volatility = min(100, volatility * 2) # 震盪大不大
            
            totalRisk = round((r_debt * 0.4) + (r_valuation * 0.4) + (r_volatility * 0.2), 2)

            return {
                "symbol": self.symbol,
                "currentPrice": round(float(current_price), 2),
                "buffettScore": float(buffettScore),
                "totalRisk": float(totalRisk),
                "pe": round(float(pe), 2),
                "roe": round(float(roe), 2),
                "momentum": float(momentum),
                "factors": {
                    "value": round(float(f_value), 1),
                    "quality": round(float(f_quality), 1),
                    "momentum": round(float(f_momentum), 1),
                    "growth": round(float(f_growth), 1)
                },
                "risks": {
                    "debt": round(float(r_debt), 1),
                    "valuation": round(float(r_valuation), 1),
                    "volatility": round(float(r_volatility), 1)
                },
                "scan_date": str(self.today)
            }
        except Exception as e:
            print(f"Error analyzing {self.symbol}: {e}")
            return None
