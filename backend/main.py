import uvicorn
import os
from backend.buffett_analyzer import app  # 從你的資料夾中匯入 FastAPI 實例

# 這個檔案是為了讓 Render 能夠輕易找到啟動點
if __name__ == "__main__":
    # 取得 Render 分配的 Port，如果在本機測試則預設 8000
    port = int(os.environ.get("PORT", 8000))
    
    # 啟動伺服器
    # host 必須是 0.0.0.0 才能讓外部連線
    uvicorn.run(app, host="0.0.0.0", port=port)
