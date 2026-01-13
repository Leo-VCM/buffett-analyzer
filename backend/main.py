import uvicorn
import os
import sys

# 確保 Python 能找到當前資料夾的路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from buffett_analyzer import app  # 因為在同一個資料夾，直接匯入即可

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # 這裡的 host 必須是 0.0.0.0，Render 才能對外連線
    uvicorn.run(app, host="0.0.0.0", port=port)
