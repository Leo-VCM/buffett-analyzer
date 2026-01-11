import json
import os
import time
import requests
import pandas as pd
from io import StringIO
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI()

# 解決跨域問題，讓你的前端可以順利呼叫
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 快取檔案設定
CACHE_FILE = "sp500_cache.json"
CACHE_EXPIRE_SECONDS = 86400  # 24小時更新一次

def get_sp500_tickers():
    """從維基百科抓取 S&P 500 名單"""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers)
        # 修正核心：使用 StringIO 避免 pandas 的警告，並抓取第一個表格
        df = pd.read_html(StringIO(res.text))[0]
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"抓取 S&P 500 名單失敗: {e}")
        return []

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Buffett Analyzer API is running!"}

@app.get("/api/sp500-analysis")
def get_analysis():
    # 1. 檢查快取是否存在且未過期
    if os.path.exists(CACHE_FILE):
        file_time = os.path.getmtime(CACHE_FILE)
        if (time.time() - file_time) < CACHE_EXPIRE_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                if cache_data.get("rankings"):
                    print("使用現有的快取數據")
                    return cache_data
    
    # 2. 若無快取，則開始分析
    try:
        all_tickers = get_sp500_tickers()
        if not all_tickers:
            return {"status": "error", "message": "Could not fetch tickers"}

        # 修正核心：先限制在 50 支，避免 Render 免費版記憶體 (512MB) 爆掉
        test_tickers = all_tickers[:50] 
        
        results = []
        for symbol in test_tickers:
            try:
                # 方便在 Render Dashboard 的 Logs 查看進度
                print(f"正在分析: {symbol}") 
                
                # 處理美股特殊代號，例如 BRK.B 轉為 BRK-B 以利 yfinance 抓取
                clean_symbol = symbol.replace('.', '-')
                analyzer = BuffettStyleAnalyzer(clean_symbol)
                data = analyzer.analyze()
                
                if data:
                    results.append(data)
                    
                # 輕微延遲，避免請求過快被 Yahoo Finance 暫時封鎖
                time.sleep(0.1) 
            except Exception as e:
                print(f"{symbol} 分析失敗: {str(e)}")
                continue
        
        if not results:
            return {"status": "error", "message": "No data successfully analyzed"}

        # 3. 根據 buffettScore 由高到低排序
        results.sort(key=lambda x: x['buffettScore'], reverse=True)

        final_data = {
            "status": "success",
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rankings": results
        }

        # 4. 寫入快取檔案
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        return final_data
        
    except Exception as e:
        print(f"主程序發生錯誤: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Render 會自動分配 PORT，若無則預設 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
