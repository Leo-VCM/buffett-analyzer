"""
yfinance 測試腳本
用於診斷 Yahoo Finance API 是否正常工作
"""
import yfinance as yf
import sys

def test_stock(symbol):
    """測試單一股票"""
    print(f"\n{'='*60}")
    print(f"測試股票: {symbol}")
    print(f"{'='*60}")
    
    try:
        # 創建 Ticker 物件
        stock = yf.Ticker(symbol)
        print(f"✅ Ticker 物件創建成功")
        
        # 測試 1: 獲取基本資訊
        print(f"\n📋 測試 1: 獲取基本資訊 (info)")
        try:
            info = stock.info
            if info:
                print(f"✅ info 獲取成功")
                print(f"   公司名稱: {info.get('longName', 'N/A')}")
                print(f"   當前價格: {info.get('currentPrice', 'N/A')}")
                print(f"   P/E 比率: {info.get('forwardPE', 'N/A')}")
                print(f"   ROE: {info.get('returnOnEquity', 'N/A')}")
            else:
                print(f"❌ info 為空")
                return False
        except Exception as e:
            print(f"❌ 獲取 info 失敗: {e}")
            return False
        
        # 測試 2: 獲取歷史數據
        print(f"\n📊 測試 2: 獲取歷史數據 (1年)")
        try:
            hist = stock.history(period="1y")
            if not hist.empty:
                print(f"✅ 歷史數據獲取成功")
                print(f"   數據天數: {len(hist)}")
                print(f"   最新收盤價: {hist['Close'].iloc[-1]:.2f}")
                print(f"   1年前價格: {hist['Close'].iloc[0]:.2f}")
                print(f"   1年漲跌幅: {((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100):.2f}%")
            else:
                print(f"❌ 歷史數據為空")
                return False
        except Exception as e:
            print(f"❌ 獲取歷史數據失敗: {e}")
            return False
        
        # 測試 3: 檢查關鍵欄位
        print(f"\n🔍 測試 3: 檢查關鍵欄位")
        required_fields = {
            'longName': info.get('longName'),
            'currentPrice': info.get('currentPrice'),
            'regularMarketPrice': info.get('regularMarketPrice'),
            'forwardPE': info.get('forwardPE'),
            'trailingPE': info.get('trailingPE'),
            'returnOnEquity': info.get('returnOnEquity'),
        }
        
        missing_fields = []
        for field, value in required_fields.items():
            if value is None or value == 0:
                missing_fields.append(field)
                print(f"   ⚠️ {field}: 缺失或為 0")
            else:
                print(f"   ✅ {field}: {value}")
        
        if missing_fields:
            print(f"\n⚠️ 警告: 部分欄位缺失，但仍可使用預設值")
        
        print(f"\n✅ {symbol} 測試通過！")
        return True
        
    except Exception as e:
        print(f"\n❌ {symbol} 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主測試函數"""
    print("="*60)
    print("yfinance 測試腳本")
    print("="*60)
    
    # 測試多支股票
    test_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
    
    results = {}
    for symbol in test_symbols:
        results[symbol] = test_stock(symbol)
    
    # 總結
    print(f"\n{'='*60}")
    print("測試總結")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for symbol, result in results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{symbol}: {status}")
    
    print(f"\n通過率: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print(f"\n🎉 所有測試通過！yfinance 工作正常")
        sys.exit(0)
    elif passed > 0:
        print(f"\n⚠️ 部分測試失敗，可能是特定股票的數據問題")
        sys.exit(1)
    else:
        print(f"\n❌ 所有測試失敗！可能是網路問題或 Yahoo Finance API 暫時無法訪問")
        sys.exit(1)

if __name__ == "__main__":
    main()
