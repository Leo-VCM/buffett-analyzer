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

# 跨域設定：對齊前端 URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 部署建議改為 https://buffett-frontend.onrender.com
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "sp500_cache.json"
CACHE_EXPIRE = 86400

def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_html(StringIO(res.text))[0]
        return df['Symbol'].tolist()
    except:
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "BRK-B", "TSLA"]

@app.get("/api/sp500-analysis")
def get_analysis():
    # 檢查快取
    if os.path.exists(CACHE_FILE):
        if (time.time() - os.path.getmtime(CACHE_FILE)) < CACHE_EXPIRE:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)

    # 執行分析
    tickers = get_sp500_tickers()[:30] # 免費版 Render 建議先跑 30 支
    rankings = []
    
    for symbol in tickers:
        analyzer = BuffettStyleAnalyzer(symbol.replace('.', '-'))
        data = analyzer.analyze()
        if data:
            rankings.append(data)
        time.sleep(0.1)

    # 排序
    rankings.sort(key=lambda x: x['buffettScore'], reverse=True)

    result = {
        "status": "success",
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rankings": rankings
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(result, f)

    return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
