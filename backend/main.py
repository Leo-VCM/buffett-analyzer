import os
import uvicorn
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# 確保你的 backend 資料夾內有 buffett_analyzer.py
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI(title="Buffett S&P 500 Analyzer API")

# 1. 解決跨域問題 (CORS) - 讓前端能順利連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定義請求資料格式 (保留原有的 POST 功能)
class StockRequest(BaseModel):
    symbols: List[str]

# --- 路由設定 ---

@app.get("/")
async def root():
    return {"message": "巴菲特風格分析 API 已啟動，S&P 500 自動分析功能就緒"}

@app.get("/api/sp500-analysis")
async def analyze_sp500_top():
    """
    自動抓取 S&P 500 前 50 支股票並進行排名
    注意：Render 免費版抓取 50 支約需 45-60 秒
    """
    try:
        print(">>> 正在從維基百科獲取 S&P 500 最新清單...")
        # 抓取維基百科表格
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = tables[0]
        
        # 取得前 50 支代碼 (通常按市值權重排序)
        # 如果 Render 經常超時，可以把 50 改成 30
        top_50_symbols = df['Symbol'].tolist()[:50]
        
        results = []
        print(f">>> 開始逐一分析這 {len(top_50_symbols)} 支股票...")
        
        for index, symbol in enumerate(top_50_symbols):
            try:
                # 處理美股代碼特殊符號 (如 BRK.B 轉為 BRK-B)
                clean_symbol = symbol.replace('.', '-')
                analyzer = BuffettStyleAnalyzer(clean_symbol)
                data = analyzer.analyze()
                results.append(data)
                
                # 每 5 支在 Log 印一次進度
                if (index + 1) % 5 == 0:
                    print(f"進度: {index + 1}/{len(top_50_symbols)} 完成")
                    
            except Exception as e:
                print(f"⚠️ 跳過 {symbol}: {str(e)}")
                continue
        
        # 依照巴菲特評分 (buffettScore) 由高到低排序
        results.sort(key=lambda x: x['buffettScore'], reverse=True)
        
        print(f"✅ 分析完畢！成功獲得 {len(results)} 支股票排名")
        return {
            "status": "success",
            "count": len(results),
            "rankings": results
        }
    except Exception as e:
        print(f"❌ 重大錯誤: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/buffett-analyze")
async def analyze_custom_stocks(request: StockRequest):
    """手動輸入代碼的分析介面 (保留備用)"""
    results = []
    print(f">>> 收到手動請求: {request.symbols}")
    for symbol in request.symbols:
        try:
            analyzer = BuffettStyleAnalyzer(symbol)
            results.append(analyzer.analyze())
        except:
            continue
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    return {"status": "success", "rankings": results}

if __name__ == "__main__":
    # 讀取雲端環境設定的 PORT，預設 10000
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
