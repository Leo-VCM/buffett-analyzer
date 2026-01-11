import json
import os
import time
import requests
import pandas as pd
from io import StringIO  # 1. 確保這行有加
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from buffett_analyzer import PortfolioScreener

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "sp500_cache.json"
CACHE_EXPIRE_SECONDS = 86400

def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    # 2. 修正核心：解決 Log 裡的 FutureWarning
    df = pd.read_html(StringIO(res.text))[0] 
    return df['Symbol'].tolist()

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Welcome!"}

@app.get("/api/sp500-analysis")
def get_analysis():
    # 檢查快取
    if os.path.exists(CACHE_FILE):
        file_time = os.path.getmtime(CACHE_FILE)
        if (time.time() - file_time) < CACHE_EXPIRE_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                # 確保快取內有數據才回傳，避免傳回 null
                if cache_data.get("rankings"):
                    return cache_data
    
    try:
        all_tickers = get_sp500_tickers()
        # 3. 修正核心：先降到 50 支，避免 Render 記憶體爆掉導致 Shutting down
        test_tickers = all_tickers[:50] 
        
        results = []
        for symbol in test_tickers:
            try:
                print(f"正在分析: {symbol}") # 方便在 Render Log 追蹤進度
                analyzer = BuffettStyleAnalyzer(symbol.replace('.', '-'))
                data = analyzer.analyze()
                if data:
                    results.append(data)
            except Exception as e:
                print(f"{symbol} 失敗: {str(e)}")
                continue
        
        if not results:
            return {"status": "error", "message": "No data found"}

        results.sort(key=lambda x: x['buffettScore'], reverse=True)

        final_data = {
            "status": "success",
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rankings": results
        }

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        return final_data
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
