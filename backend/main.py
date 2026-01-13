"""
Buffett Analyzer API 啟動檔
用於 Render 部署
"""
import uvicorn
import os
import sys
import logging

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 確保 Python 能找到當前資料夾的模組
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 載入 FastAPI app
try:
    from buffett_analyzer import app
    logger.info("✅ buffett_analyzer 模組載入成功")
except ImportError as e:
    logger.error(f"❌ 無法載入 buffett_analyzer: {e}")
    logger.error(f"當前目錄: {current_dir}")
    logger.error(f"Python 路徑: {sys.path}")
    logger.error(f"目錄內容: {os.listdir(current_dir)}")
    sys.exit(1)

if __name__ == "__main__":
    # Render 會自動設定 PORT 環境變數
    port = int(os.environ.get("PORT", 10000))
    
    logger.info("=" * 60)
    logger.info("🚀 啟動 Buffett Analyzer API")
    logger.info(f"📍 監聽端口: {port}")
    logger.info(f"🌐 主機: 0.0.0.0 (Render 公開訪問)")
    logger.info(f"📚 API 文檔: http://0.0.0.0:{port}/docs")
    logger.info("=" * 60)
    
    # 啟動服務
    # 重要：host 必須是 0.0.0.0，否則 Render 無法對外提供服務
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=True,
        timeout_keep_alive=120  # 保持連線 120 秒
    )
