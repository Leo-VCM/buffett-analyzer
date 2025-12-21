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
        # 抓取基本面，若抓不到則給 0
        return {
            'currentPrice': info.get('currentPrice', 0),
            'pe': info.get('trailingPE', 0),
            'pb': info.get('priceToBook', 0),
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            'debtToEquity': info.get('debtToEquity', 0) if info.get('debtToEquity') else 0,
            'currentRatio': info.get('currentRatio', 0),
            'profitMargin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
            'dividendYield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            'revenueGrowth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
            'epsGrowth': self.calculate_eps_growth()
        }
    
    def calculate_eps_growth(self):
        try:
            financials = self.stock.financials
            if financials.empty: return 0
            net_income = financials.loc['Net Income']
            if len(net_income) >= 2:
                growth = ((net_income.iloc[0] - net_income.iloc[1]) / abs(net_income.iloc[1])) * 100
                return growth
            return 0
        except: return 0
    
    def get_real_technical(self):
        hist = self.stock.history(period='6mo')
        if hist.empty: return {'rsi': 50, 'volatility': 20, 'trend': 'DOWN', 'momentum': 50}
        
        # 簡單波動率計算
        volatility = hist['Close'].pct_change().std() * np.sqrt(252) * 100
        # 趨勢判斷 (20日均線 vs 60日均線)
        ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
        ma60 = hist['Close'].rolling(window=60).mean().iloc[-1]
        
        return {
            'rsi': 50, # 簡化處理
            'volatility': round(volatility, 2),
            'trend': 'UP' if ma20 > ma60 else 'DOWN',
            'momentum': 50 # 簡化處理
        }

    def analyze(self):
        fund = self.get_real_fundamentals()
        tech = self.get_real_technical()
        
        # 1. 風險計算
        debt_risk = 30 if fund['debtToEquity'] > 1.5 else fund['debtToEquity'] * 15
        val_risk = 25 if fund['pe'] > 30 else fund['pe'] * 0.7
        total_risk = min(100, debt_risk + val_risk + (tech['volatility'] * 0.5))
        
        # 2. 價值評分 (低PE/PB加分)
        val_score = (100 if fund['pe'] < 15 else 60) * 0.5 + (100 if fund['pb'] < 2 else 60) * 0.5
        
        # 3. 品質評分 (高ROE加分)
        qual_score = min(100, fund['roe'] * 4)
        
        # 4. 綜合巴菲特分數
        buffett_score = (val_score * 0.4) + (qual_score * 0.4) + ((100 - total_risk) * 0.2)
        
        return {
            'symbol': self.symbol,
            'buffettScore': round(buffett_score, 2),
            'fundamentals': fund,
            'risk': {'totalRisk': round(total_risk, 2), 'level': 'LOW' if total_risk < 40 else 'HIGH'},
            'value': round(val_score, 2),
            'quality': round(qual_score, 2),
            'recommendation': self.get_rec(buffett_score, total_risk)
        }

    def get_rec(self, score, risk):
        if score > 70 and risk < 40: return {'text': '強力買入', 'color': 'text-green-600', 'bg': 'bg-green-100'}
        if score > 50: return {'text': '持有觀察', 'color': 'text-blue-600', 'bg': 'bg-blue-100'}
        return {'text': '謹慎評估', 'color': 'text-yellow-600', 'bg': 'bg-yellow-100'}
      
