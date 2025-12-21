import os
import uvicorn
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# 確保你的 backend 資料夾內有 buffett_analyzer.py
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI(title="Buffett Style Stock Analyzer API")

# 1. 解決跨域問題 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定義請求資料格式
class StockRequest(BaseModel):
    symbols: List[str]

# --- 路由設定 ---

@app.get("/")
async def root():
    return {"message": "巴菲特風格分析 API 已啟動"}

@app.get("/test-analyze")
async def test_analyze():
    """測試單一股票 (AAPL)"""
    analyzer = BuffettStyleAnalyzer("AAPL")
    return analyzer.analyze()

@app.get("/api/sp500-analysis")
async def analyze_sp500_top():
    """
    自動抓取 S&P 500 前 50 支股票並進行排名
    注意：這需要大約 30-60 秒，請耐心等待
    """
    try:
        print("正在從維基百科獲取 S&P 500 清單...")
        # 抓取維基百科表格
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = tables[0]
        # 取前 50 支
        top_50_symbols = df['Symbol'].tolist()[:50]
        
        results = []
        print(f"開始分析前 50 支股票...")
        
        for symbol in top_50_symbols:
            try:
                # 處理美股代碼特殊符號 (如 BRK.B 轉為 BRK-B)
                clean_symbol = symbol.replace('.', '-')
                analyzer = BuffettStyleAnalyzer(clean_symbol)
                data = analyzer.analyze()
                results.append(data)
                print(f"✅ {clean_symbol} 分析成功")
            except Exception as e:
                print(f"❌ {symbol} 忽略，原因: {e}")
                continue
        
        # 依分數排序
        results.sort(key=lambda x: x['buffettScore'], reverse=True)
        
        print(f"全部分析完成，共成功獲取 {len(results)} 支股票數據")
        return {
            "status": "success",
            "count": len(results),
            "rankings": results
        }
    except Exception as e:
        print(f"重大錯誤: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/buffett-analyze")
async def analyze_stocks(request: StockRequest):
    """
    接收自定義股票代碼列表進行分析
    """
    results = []
    print(f"收到自定義分析請求: {request.symbols}")
    
    for symbol in request.symbols:
        try:
            analyzer = BuffettStyleAnalyzer(symbol)
            result = analyzer.analyze()
            results.append(result)
        except Exception as e:
            print(f"分析 {symbol} 時出錯: {e}")
            continue
    
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    return {
        "status": "success",
        "rankings": results
    }

if __name__ == "__main__":
    # 2. 雲端部署關鍵：讀取環境變數中的 PORT
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
  
