import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# 確保你已經上傳了之前定義的 buffett_analyzer.py
from buffett_analyzer import BuffettStyleAnalyzer

app = FastAPI(title="Buffett Style Stock Analyzer API")

# 1. 解決跨域問題 (CORS)
# 這允許你的前端網頁可以跨網域存取這個後端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生產環境建議改為你的前端網址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定義請求資料格式
class StockRequest(BaseModel):
    symbols: List[str]

@app.get("/")
async def root():
    return {"message": "巴菲特風格分析 API 已啟動"}

@app.post("/api/buffett-analyze")
async def analyze_stocks(request: StockRequest):
    """
    接收股票代碼列表，並進行即時分析
    """
    results = []
    
    for symbol in request.symbols:
        try:
            # 初始化分析器並執行分析
            analyzer = BuffettStyleAnalyzer(symbol)
            result = analyzer.analyze()
            results.append(result)
        except Exception as e:
            # 如果某支股票分析失敗，跳過並記錄錯誤
            print(f"分析 {symbol} 時出錯: {e}")
            continue
    
    # 根據巴菲特評分由高到低排序
    results.sort(key=lambda x: x['buffettScore'], reverse=True)
    
    return {
        "status": "success",
        "rankings": results
    }

if __name__ == "__main__":
    # 2. 雲端部署關鍵：讀取環境變數中的 PORT
    # 如果環境中沒有設定 PORT (例如在自己電腦跑)，則預設使用 10000
    port = int(os.environ.get("PORT", 10000))
    
    # 啟動伺服器
    uvicorn.run(app, host="0.0.0.0", port=port)
  
