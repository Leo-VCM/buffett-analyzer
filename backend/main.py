import json
import os
import time
import requests
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI()

# 解決跨域問題
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "sp500_cache.json"
# 緩存 24 小時
CACHE_EXPIRE_SECONDS = 86400

def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    df = pd.read_html(res.text)[0]
    return df['Symbol'].tolist()

@app.get("/api/sp500-analysis")
def get_analysis():
    # 1. 檢查快取
    if os.path.exists(CACHE_FILE):
        file_time = os.path.getmtime(CACHE_FILE)
        if (time.time() - file_time) < CACHE_EXPIRE_SECONDS:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)

    # 2. 執行分析 (若無快取)
    try:
        all_tickers = get_sp500_tickers()
        test_tickers = all_tickers[:50] # 為了速度，先取前 50 支
        
        results = []
        for symbol in test_tickers:
            try:
                # 替換 '.' 為 '-' 以符合 yfinance 格式 (例如 BRK.B -> BRK-B)
                analyzer = BuffettStyleAnalyzer(symbol.replace('.', '-'))
                results.append(analyzer.analyze())
            except:
                continue
        
        # 排序：分數高排前面
        results.sort(key=lambda x: x['buffettScore'], reverse=True)

        final_data = {
            "status": "success",
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rankings": results
        }

        # 3. 寫入快取
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        return final_data
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
