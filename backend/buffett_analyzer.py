import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
from pathlib import Path

class PortfolioScreener:
    def __init__(self, data_folder='portfolio_data'):
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)
        self.today = datetime.now().date()
        
    def get_sp500_tickers(self):
        """獲取 S&P 500 成分股列表"""
        # 使用常見的大型股票作為示例，實際應用可以從維基百科或其他來源抓取
        tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
            'UNH', 'JNJ', 'V', 'WMT', 'JPM', 'PG', 'MA', 'HD', 'CVX', 'MRK',
            'ABBV', 'KO', 'PEP', 'AVGO', 'COST', 'LLY', 'MCD', 'CSCO', 'TMO',
            'ACN', 'ABT', 'DIS', 'ADBE', 'VZ', 'NFLX', 'CMCSA', 'NKE', 'DHR',
            'TXN', 'INTC', 'NEE', 'UPS', 'PM', 'ORCL', 'CRM', 'QCOM', 'HON',
            'WFC', 'IBM', 'AMD', 'AMGN', 'CAT', 'RTX', 'GE', 'LOW', 'SBUX',
            'INTU', 'BA', 'AMAT', 'SPGI', 'BLK', 'PLD', 'GS', 'AXP', 'NOW',
            'DE', 'ELV', 'BKNG', 'GILD', 'SYK', 'TJX', 'ADP', 'MMC', 'MDLZ',
            'VRTX', 'C', 'ADI', 'ZTS', 'REGN', 'AMT', 'CI', 'PGR', 'CVS',
            'CB', 'MO', 'DUK', 'SO', 'ISRG', 'SCHW', 'BMY', 'BDX', 'PNC',
            'LRCX', 'ETN', 'TGT', 'CL', 'USB', 'SLB', 'MU', 'EQIX', 'BSX'
        ]
        return tickers[:100]  # 返回前100個作為樣本
    
    def calculate_momentum(self, hist):
        """計算動能指標（12個月回報）"""
        try:
            if len(hist) < 252:
                return 0
            current_price = hist['Close'].iloc[-1]
            price_1y_ago = hist['Close'].iloc[-252]
            momentum = ((current_price - price_1y_ago) / price_1y_ago) * 100
            return round(momentum, 2)
        except:
            return 0
    
    def get_fundamental_data(self, symbol):
        """獲取基本面數據"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period='1y')
            
            if hist.empty or len(hist) < 60:
                return None
            
            # ROE 處理
            raw_roe = info.get('returnOnEquity', 0)
            if raw_roe is None:
                roe_val = 0
            elif abs(raw_roe) < 1.0:
                roe_val = raw_roe * 100
            else:
                roe_val = raw_roe
            
            # 基本面指標
            data = {
                'symbol': symbol,
                'currentPrice': info.get('currentPrice', 0),
                'pe': info.get('forwardPE') or info.get('trailingPE') or 0,
                'pb': info.get('priceToBook', 0),
                'roe': round(roe_val, 2),
                'debtToEquity': info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0,
                'profitMargin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
                'revenueGrowth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
                'momentum': self.calculate_momentum(hist),
                'volatility': hist['Close'].pct_change().std() * np.sqrt(252) * 100,
            }
            
            return data
        except Exception as e:
            print(f"Error fetching {symbol}: {str(e)}")
            return None
    
    def calculate_multi_factor_score(self, data):
        """多因子評分系統"""
        scores = {}
        
        # 1. 價值因子 (Value) - 40%
        pe_score = 100 if 0 < data['pe'] < 15 else (70 if data['pe'] < 25 else 30)
        pb_score = 100 if 0 < data['pb'] < 1.5 else 50
        scores['value'] = (pe_score * 0.6 + pb_score * 0.4)
        
        # 2. 質量因子 (Quality) - 30%
        if data['roe'] > 20:
            roe_score = 100
        elif data['roe'] > 0:
            roe_score = data['roe'] * 5
        else:
            roe_score = 0
        
        margin_score = min(100, data['profitMargin'] * 10) if data['profitMargin'] > 0 else 0
        scores['quality'] = (roe_score * 0.7 + margin_score * 0.3)
        
        # 3. 動能因子 (Momentum) - 20%
        if data['momentum'] > 0:
            scores['momentum'] = min(100, data['momentum'])
        else:
            scores['momentum'] = 0  # 負動能直接排除
        
        # 4. 成長因子 (Growth) - 10%
        scores['growth'] = min(100, max(0, data['revenueGrowth'])) if data['revenueGrowth'] > 0 else 0
        
        # 綜合評分
        total_score = (
            scores['value'] * 0.4 +
            scores['quality'] * 0.3 +
            scores['momentum'] * 0.2 +
            scores['growth'] * 0.1
        )
        
        return total_score, scores
    
    def calculate_risk_components(self, data):
        """計算三大風險成分"""
        # 1. 債務風險 (0-40分)
        debt_risk = min(40, data['debtToEquity'] * 10)
        
        # 2. 估值風險 (0-40分)
        val_risk = min(40, (data['pe'] / 40) * 40) if data['pe'] > 0 else 40
        
        # 3. 波動性風險 (0-20分)
        volatility_risk = min(20, data['volatility'] * 0.2)
        
        total_risk = debt_risk + val_risk + volatility_risk
        
        return {
            'debt_risk': round(debt_risk, 2),
            'valuation_risk': round(val_risk, 2),
            'volatility_risk': round(volatility_risk, 2),
            'total_risk': round(total_risk, 2)
        }
    
    def filter_portfolio(self, tickers, top_n=12):
        """篩選投資組合"""
        results = []
        
        print(f"開始分析 {len(tickers)} 支股票...")
        for i, ticker in enumerate(tickers, 1):
            print(f"進度: {i}/{len(tickers)} - {ticker}")
            
            data = self.get_fundamental_data(ticker)
            if data is None:
                continue
            
            # 第一輪過濾：排除負動能
            if data['momentum'] <= 0:
                continue
            
            # 計算多因子評分
            total_score, factor_scores = self.calculate_multi_factor_score(data)
            
            # 計算風險成分
            risk_components = self.calculate_risk_components(data)
            
            # 第二輪過濾：風險控制
            # 單一風險 < 20%
            if (risk_components['debt_risk'] > 20 or 
                risk_components['valuation_risk'] > 20 or 
                risk_components['volatility_risk'] > 20):
                continue
            
            # 總風險 < 50%
            if risk_components['total_risk'] > 50:
                continue
            
            # 合併結果
            result = {
                **data,
                'total_score': round(total_score, 2),
                'factor_scores': factor_scores,
                'risk_components': risk_components,
                'scan_date': str(self.today)
            }
            
            results.append(result)
        
        # 按總評分排序，取前 N 名
        results.sort(key=lambda x: x['total_score'], reverse=True)
        return results[:top_n]
    
    def save_to_local(self, portfolio):
        """保存數據到本地"""
        filename = self.data_folder / f"portfolio_{self.today}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        
        print(f"\n數據已保存到: {filename}")
        
        # 保存最新版本
        latest_file = self.data_folder / "portfolio_latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
    
    def load_from_local(self):
        """從本地載入最新數據"""
        latest_file = self.data_folder / "portfolio_latest.json"
        
        if not latest_file.exists():
            return None
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 檢查是否需要更新
        if data and len(data) > 0:
            saved_date = datetime.strptime(data[0]['scan_date'], '%Y-%m-%d').date()
            if saved_date == self.today:
                print(f"使用今日已保存的數據 ({saved_date})")
                return data
            else:
                print(f"本地數據已過期 ({saved_date})，需要重新掃描")
        
        return None
    
    def generate_report(self, portfolio):
        """生成報告"""
        print("\n" + "="*80)
        print(f"投資組合報告 - {self.today}")
        print("="*80)
        print(f"\n符合條件的股票數量: {len(portfolio)}")
        print("\n前 12 名投資組合:")
        print("-"*80)
        
        for i, stock in enumerate(portfolio, 1):
            print(f"\n【第 {i} 名】{stock['symbol']} - 總分: {stock['total_score']}")
            print(f"  當前價格: ${stock['currentPrice']:.2f}")
            print(f"  基本面: PE={stock['pe']:.2f}, PB={stock['pb']:.2f}, ROE={stock['roe']:.2f}%")
            print(f"  動能: {stock['momentum']:.2f}%")
            print(f"  因子評分: 價值={stock['factor_scores']['value']:.1f}, "
                  f"質量={stock['factor_scores']['quality']:.1f}, "
                  f"動能={stock['factor_scores']['momentum']:.1f}, "
                  f"成長={stock['factor_scores']['growth']:.1f}")
            print(f"  風險成分: 債務={stock['risk_components']['debt_risk']:.1f}, "
                  f"估值={stock['risk_components']['valuation_risk']:.1f}, "
                  f"波動={stock['risk_components']['volatility_risk']:.1f} "
                  f"(總計={stock['risk_components']['total_risk']:.1f})")
        
        print("\n" + "="*80)
    
    def run(self, force_update=False):
        """主執行函數"""
        # 檢查是否需要更新
        if not force_update:
            cached_data = self.load_from_local()
            if cached_data:
                self.generate_report(cached_data)
                return cached_data
        
        # 獲取股票列表
        tickers = self.get_sp500_tickers()
        
        # 篩選投資組合
        portfolio = self.filter_portfolio(tickers, top_n=12)
        
        # 保存到本地
        self.save_to_local(portfolio)
        
        # 生成報告
        self.generate_report(portfolio)
        
        return portfolio

# 使用範例
if __name__ == "__main__":
    screener = PortfolioScreener()
    
    # 執行篩選（force_update=True 強制更新，False 則使用當日快取）
    portfolio = screener.run(force_update=False)
    
    # 轉換為 DataFrame 方便分析
    df = pd.DataFrame(portfolio)
    print(f"\n投資組合已生成，共 {len(df)} 支股票")
