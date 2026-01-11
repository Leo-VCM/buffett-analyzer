import yfinance as yf
import numpy as np
import logging

logger = logging.getLogger(__name__)

class BuffettStyleAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.stock = yf.Ticker(symbol)

    def analyze(self):
        try:
            info = self.stock.info
            # 取得 1 年歷史數據計算動能與波動
            hist = self.stock.history(period="1y")
            if hist.empty: return None

            # 1. 基礎數據
            price = info.get('currentPrice', 0)
            
            # ROE 歸一化處理
            raw_roe = info.get('returnOnEquity', 0)
            roe = (raw_roe * 100) if raw_roe and abs(raw_roe) < 1 else (raw_roe or 0)
            
            pe = info.get('forwardPE') or info.get('trailingPE') or 0
            debt_to_equity = info.get('debtToEquity', 0)

            # 2. 計算動能 (Momentum)
            close_prices = hist['Close']
            momentum = ((close_prices.iloc[-1] - close_prices.iloc[0]) / close_prices.iloc[0]) * 100
            
            # 3. 計算因子評分 (Factors: 0-100)
            # 價值: PE越低分越高
            v_score = 100 if 0 < pe < 15 else (70 if pe < 25 else 30)
            # 質量: ROE越高分越高
            q_score = min(100, roe * 4) if roe > 0 else 0
            # 動能: 轉化為 0-100 分
            m_score = max(0, min(100, momentum + 20))
            # 成長: 營收成長
            rev_growth = info.get('revenueGrowth', 0) * 100
            g_score = max(0, min(100, rev_growth))

            # 綜合評分 (Buffett Score)
            buffett_score = (v_score * 0.4 + q_score * 0.3 + m_score * 0.2 + g_score * 0.1)

            # 4. 風險分析 (Risks: 0-100)
            debt_r = min(100, debt_to_equity / 2) # 假設 D/E > 200 為極高風險
            val_r = min(100, (pe / 40) * 100) if pe > 0 else 50
            vol_r = hist['Close'].pct_change().std() * np.sqrt(252) * 100
            
            total_risk = (debt_r * 0.4 + val_r * 0.4 + vol_r * 0.2)

            # 5. 回傳對齊前端的結構
            return {
                "symbol": self.symbol,
                "currentPrice": round(price, 2),
                "buffettScore": round(buffett_score, 1),
                "momentum": round(momentum, 2),
                "totalRisk": round(total_risk, 1),
                "roe": round(roe, 2),
                "pe": round(pe, 2),
                "factors": {
                    "value": round(v_score, 0),
                    "quality": round(q_score, 0),
                    "momentum": round(m_score, 0),
                    "growth": round(g_score, 0)
                },
                "risks": {
                    "debt": round(debt_r, 1),
                    "valuation": round(val_r, 1),
                    "volatility": round(vol_r, 1)
                }
            }
        except Exception as e:
            logger.error(f"Error analyzing {self.symbol}: {e}")
            return None
