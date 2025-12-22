import os
import uvicorn
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing impoimport os
import uvicorn
import pandas as pd
import requests  # 新增：用來發送帶有 Header 的請求
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# 確保你的 backend 資料夾內有 buffett_analyzer.py
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI(title="Buffett S&P 500 Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockRequest(BaseModel):
    symbols: List[str]

@app.get("/")
async def root():
    return {"message": "巴菲特風格分析 API 已啟動，S&P 500 自動分析功能就緒"}

@app.get("/api/sp500-analysis")
async def analyze_sp500_top():
    try:
        print(">>> 正在獲取 S&P 500 清單 (解決 403 Forbidden 問題)...")
        
        # 關鍵修正：偽裝成一般瀏覽器訪問維基百科
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"status": "error", "message": f"維基百科拒絕連線: {response.status_code}"}

        # 使用 pandas 解析 response 的文字內容
        tables = pd.read_html(response.text)
        df = tables[0]
        
        # 先取前 30 支測試（最穩定），成功後再改回 50
        top_symbols = df['Symbol'].tolist()[:30]
        
        results = []
        print(f">>> 開始分析這 {len(top_symbols)} 支股票...")
        
        for index, symbol in enumerate(top_symbols):
            try:
                clean_symbol = symbol.replace('.', '-')
                analyzer = BuffettStyleAnalyzer(clean_symbol)
                data = analyzer.analyze()
                results.append(data)
                
                if (index + 1) % 5 == 0:
                    print(f"進度: {index + 1}/{len(top_symbols)} 完成")
            except Exception as e:
                print(f"⚠️ 跳過 {symbol}: {str(e)}")
                continue
        
        results.sort(key=lambda x: x['buffettScore'], reverse=True)
        print(f"✅ 分析完畢！成功獲得 {len(results)} 支股票排名")
        return {"status": "success", "count": len(results), "rankings": results}

    except Exception as e:
        print(f"❌ 重大錯誤: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/buffett-analyze")
async def analyze_custom_stocks(request: StockRequest):
    results = []
    for symbol in request.symbols:
        try:
            analyzer = BuffettStyleAnalyzer(symbol)
            results.append(analyzer.analyze())
        except: continue
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    return {"status": "success", "rankings": results}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
