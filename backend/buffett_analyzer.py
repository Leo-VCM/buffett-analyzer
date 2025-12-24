import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

class BuffettStyleAnalyzer:
    def __init__(self, symbol):
        self.symbol = symbol
        self.stock = yf.Ticker(symbol)
        
    def get_real_fundamentals(self):
        info = self.stock.info
        
        # --- 修正 ROE 邏輯：處理 yfinance 單位不一的問題 ---
        raw_roe = info.get('returnOnEquity', 0)
        if raw_roe is None:
            roe_val = 0
        elif abs(raw_roe) < 1.0: # 如果是 0.28 這種小數
            roe_val = raw_roe * 100
        else: # 如果已經是 28.8 這種整數
            roe_val = raw_roe
            
        return {
            'currentPrice': info.get('currentPrice', 0),
            'pe': info.get('forwardPE') or info.get('trailingPE') or 0,
            'pb': info.get('priceToBook', 0),
            'roe': round(roe_val, 2),
            'debtToEquity': info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0, # yfinance 的債權比通常是百分比
            'currentRatio': info.get('currentRatio', 0),
            'profitMargin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
            'dividendYield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            'revenueGrowth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
            'epsGrowth': self.calculate_eps_growth()
        }
    
    def calculate_eps_growth(self):
        try:
            financials = self.stock.financials
            if financials.empty or 'Net Income' not in financials.index: return 0
            net_income = financials.loc['Net Income']
            if len(net_income) >= 2:
                prev = abs(net_income.iloc[1])
                if prev == 0: return 0
                growth = ((net_income.iloc[0] - net_income.iloc[1]) / prev) * 100
                return round(growth, 2)
            return 0
        except: return 0
    
    def get_real_technical(self):
        # 增加緩衝，防止數據不足
        hist = self.stock.history(period='1y')
        if len(hist) < 60: return {'rsi': 50, 'volatility': 20, 'trend': 'DOWN', 'momentum': 50}
        
        volatility = hist['Close'].pct_change().std() * np.sqrt(252) * 100
        ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
        ma60 = hist['Close'].rolling(window=60).mean().iloc[-1]
        
        return {
            'rsi': 50, 
            'volatility': round(volatility, 2),
            'trend': 'UP' if ma20 > ma60 else 'DOWN',
            'momentum': 50
        }

    def analyze(self):
        fund = self.get_real_fundamentals()
        tech = self.get_real_technical()
        
        # 1. 風險計算 (更嚴謹的權重)
        # 債務比 > 2 通常被視為高風險
        debt_risk = min(40, fund['debtToEquity'] * 10)
        # PE > 40 為估值過高風險
        val_risk = min(40, (fund['pe'] / 40) * 40) if fund['pe'] > 0 else 40
        total_risk = min(100, debt_risk + val_risk + (tech['volatility'] * 0.2))
        
        # 2. 價值評分 (低PE/PB加分)
        # 巴菲特喜歡 PE < 15, PB < 1.5
        pe_score = 100 if 0 < fund['pe'] < 15 else (70 if fund['pe'] < 25 else 30)
        pb_score = 100 if 0 < fund['pb'] < 1.5 else 50
        val_score = (pe_score * 0.6) + (pb_score * 0.4)
        
        # 3. 品質評分 (修正 ROE 評分邏輯)
        # 巴菲特準則：ROE > 15% 是優秀，這裡我們讓 20% 拿滿分
        if fund['roe'] > 20:
            qual_score = 100
        elif fund['roe'] > 0:
            qual_score = fund['roe'] * 5 # 15% -> 75分
        else:
            qual_score = 0
            
        # 4. 綜合巴菲特分數
        buffett_score = (val_score * 0.4) + (qual_score * 0.4) + ((100 - total_risk) * 0.2)
        
        return {
            'symbol': self.symbol,
            'buffettScore': round(buffett_score, 2),
            'fundamentals': fund,
            'risk': {'totalRisk': round(total_risk, 2), 'level': 'LOW' if total_risk < 45 else 'HIGH'},
            'value': round(val_score, 2),
            'quality': round(qual_score, 2),
            'recommendation': self.get_rec(buffett_score, total_risk)
        }

    def get_rec(self, score, risk):
        if score > 75 and risk < 40: return {'text': '強力買入', 'color': 'text-green-600', 'bg': 'bg-green-100'}
        if score > 55: return {'text': '持有觀察', 'color': 'text-blue-600', 'bg': 'bg-blue-100'}
        return {'text': '謹慎評估', 'color': 'text-red-600', 'bg': 'bg-red-100'}
