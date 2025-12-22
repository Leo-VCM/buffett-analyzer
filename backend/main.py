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
    try:
        print(">>> 正在獲取 S&P 500 清單 (加上 User-Agent)...")
        
        # 解決 403 Forbidden 的關鍵：偽裝成一般瀏覽器
        import requests
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers)
        tables = pd.read_html(response.text)
        df = tables[0]
        
        # 取得前 30 支（先改為 30 支確保穩定性，成功後再改回 50）
        top_symbols = df['Symbol'].tolist()[:30]
        
        results = []
        for index, symbol in enumerate(top_symbols):
            try:
                clean_symbol = symbol.replace('.', '-')
                analyzer = BuffettStyleAnalyzer(clean_symbol)
                results.append(analyzer.analyze())
                if (index + 1) % 5 == 0:
                    print(f"進度: {index + 1}/{len(top_symbols)}")
            except:
                continue
        
        results.sort(key=lambda x: x['buffettScore'], reverse=True)
        return {"status": "success", "count": len(results), "rankings": results}
        
    except Exception as e:
        print(f"❌ 錯誤原因: {e}")
        return {"status": "error", "message": f"數據獲取失敗: {str(e)}"}
        
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
