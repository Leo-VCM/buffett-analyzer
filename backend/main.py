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
    try:
        res = requests.get(url, headers=headers)
        df = pd.read_html(StringIO(res.text))[0]
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Buffett Multi-Factor API"}

@app.get("/api/sp500-analysis")
def get_analysis():
    # 1. 讀取快取
    if os.path.exists(CACHE_FILE):
        file_time = os.path.getmtime(CACHE_FILE)
        if (time.time() - file_time) < CACHE_EXPIRE_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("rankings"):
                    return data
    
    # 2. 執行分析
    try:
        all_tickers = get_sp500_tickers()
        # Render 免費版建議跑 30-50 支，避免超時與記憶體溢出
        test_tickers = all_tickers[:40] 
        
        results = []
        for symbol in test_tickers:
            print(f"Analyzing: {symbol}")
            # 處理 BRK.B 這種代號
            analyzer = BuffettStyleAnalyzer(symbol.replace('.', '-'))
            data = analyzer.analyze()
            if data:
                results.append(data)
            time.sleep(0.2) # 禮貌性延遲
        
        if not results:
            return {"status": "error", "message": "Analysis returned empty"}

        # 按分數排序
        results.sort(key=lambda x: x['buffettScore'], reverse=True)

        final_data = {
            "status": "success",
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rankings": results
        }

        # 寫入快取
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        return final_data
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
