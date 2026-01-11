import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

class BuffettStyleAnalyzer:
    def __init__(self, symbol):
        """
        初始化分析器
        :param symbol: 股票代號 (由 main.py 傳入)
        """
        self.symbol = symbol
        self.today = datetime.now().date()
        
    def calculate_momentum(self, hist):
        """計算動能指標（12個月回報）"""
        try:
            if len(hist) < 252:
                return 0
            current_price = hist['Close'].iloc[-1]
            price_1y_ago = hist['Close'].iloc[-252]
            momentum = ((current_price - price_1y_ago) / price_1y_ago) * 100
            return round(float(momentum), 2)
        except:
            return 0
    
    def get_fundamental_data(self):
        """獲取單一股票的基本面數據"""
        try:
            stock = yf.Ticker(self.symbol)
            info = stock.info
            hist = stock.history(period='1y')
            
            if hist.empty or len(hist) < 60:
                return None
            
            # ROE 處理 (處理小數與百分比格式不一的問題)
            raw_roe = info.get('returnOnEquity', 0)
            if raw_roe is None:
                roe_val = 0
            elif abs(raw_roe) < 1.0:
                roe_val = raw_roe * 100
            else:
                roe_val = raw_roe
            
            data = {
                'symbol': self.symbol,
                'currentPrice': info.get('currentPrice', 0),
                'pe': info.get('forwardPE') or info.get('trailingPE') or 0,
                'pb': info.get('priceToBook', 0),
                'roe': round(float(roe_val), 2),
                'debtToEquity': (info.get('debtToEquity', 0) / 100) if info.get('debtToEquity') else 0,
                'profitMargin': (info.get('profitMargins', 0) * 100) if info.get('profitMargins') else 0,
                'revenueGrowth': (info.get('revenueGrowth', 0) * 100) if info.get('revenueGrowth') else 0,
                'momentum': self.calculate_momentum(hist),
                'volatility': float(hist['Close'].pct_change().std() * np.sqrt(252) * 100) if len(hist) > 1 else 0,
            }
            return data
        except Exception as e:
            print(f"Error fetching {self.symbol}: {str(e)}")
            return None

    def calculate_multi_factor_score(self, data):
        """多因子評分系統 - 產出 buffettScore"""
        scores = {}
        
        # 1. 價值因子 (Value) - 40%
        pe_score = 100 if 0 < data['pe'] < 15 else (70 if data['pe'] < 25 else 30)
        pb_score = 100 if 0 < data['pb'] < 1.5 else 50
        scores['value'] = (pe_score * 0.6 + pb_score * 0.4)
        
        # 2. 質量因子 (Quality) - 30%
        roe_score = 100 if data['roe'] > 20 else (max(0, data['roe'] * 5))
        margin_score = min(100, data['profitMargin'] * 10) if data['profitMargin'] > 0 else 0
        scores['quality'] = (roe_score * 0.7 + margin_score * 0.3)
        
        # 3. 動能因子 (Momentum) - 20%
        scores['momentum'] = min(100, max(0, data['momentum']))
        
        # 4. 成長因子 (Growth) - 10%
        scores['growth'] = min(100, max(0, data['revenueGrowth']))
        
        total_score = (
            scores['value'] * 0.4 +
            scores['quality'] * 0.3 +
            scores['momentum'] * 0.2 +
            scores['growth'] * 0.1
        )
        return round(total_score, 2)

    def analyze(self):
        """
        對接 main.py 的主核心方法
        """
        data = self.get_fundamental_data()
        if not data:
            return None
            
        # 計算總分 (對應 main.py 排序用的 key)
        data['buffettScore'] = self.calculate_multi_factor_score(data)
        data['scan_date'] = str(self.today)
        return data
