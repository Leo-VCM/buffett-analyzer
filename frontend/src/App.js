import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, Shield, Calendar, RefreshCw, DollarSign } from 'lucide-react';

// 注意：部署到 Render 後，記得在 Render 的 Environment Variables 設定 REACT_APP_API_URL
const API_BASE_URL = "https://buffett-analyzer.onrender.com";

function App() {
  const [rankings, setRankings] = useState([]);
  const [isRanking, setIsRanking] = useState(false);
  const [lastUpdateTime, setLastUpdateTime] = useState(null);

  const startAnalysis = async () => {
    setIsRanking(true);
    try {
      // 呼叫你的 FastAPI 後端實體數據
      const response = await fetch(`${API_BASE_URL}//api/buffett-analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: ['AAPL', 'TSLA', 'NVDA', 'BRK-B', 'MSFT', 'GOOGL', 'AMZN'] })
      });

      if (!response.ok) throw new Error("伺服器連線失敗");
      
      const data = await response.json();
      setRankings(data.rankings);
      setLastUpdateTime(new Date());
    } catch (error) {
      console.error("分析錯誤:", error);
      alert("無法連線到後端 API，請確認 Render 後端是否已啟動，且環境變數設定正確。");
    } finally {
      setIsRanking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 font-sans text-slate-900">
      <div className="max-w-2xl mx-auto">
        {/* 標題區 */}
        <header className="py-8 text-center">
          <div className="inline-block p-3 bg-blue-600 rounded-2xl mb-4 shadow-lg shadow-blue-200">
            <DollarSign className="text-white" size={32} />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">巴菲特評分系統</h1>
          <p className="text-slate-500 mt-2">真實財務數據 · 價值投資邏輯</p>
        </header>

        {/* 控制面板 */}
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 p-6 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Calendar size={16} />
            <span className="text-sm font-medium">
              {lastUpdateTime ? lastUpdateTime.toLocaleString() : "今日尚未分析"}
            </span>
          </div>
          <button 
            onClick={startAnalysis}
            disabled={isRanking}
            className="w-full sm:w-auto bg-blue-600 text-white px-8 py-3 rounded-2xl font-bold hover:bg-blue-700 active:scale-95 transition-all disabled:bg-slate-200 disabled:text-slate-400 flex items-center justify-center gap-2 shadow-lg shadow-blue-100"
          >
            {isRanking ? <RefreshCw className="animate-spin" size={20} /> : <Activity size={20} />}
            {isRanking ? "數據運算中" : "開始即時分析"}
          </button>
        </div>

        {/* 股票列表 */}
        <div className="grid gap-4">
          {rankings.length > 0 ? (
            rankings.map((stock, index) => (
              <div key={stock.symbol} className="bg-white p-5 rounded-3xl shadow-sm border border-slate-50 flex items-center gap-4 hover:border-blue-200 transition-colors">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-slate-50 text-slate-300 font-black italic">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-bold">{stock.symbol}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${stock.recommendation.bg} ${stock.recommendation.color}`}>
                      {stock.recommendation.text}
                    </span>
                  </div>
                  <div className="flex gap-4 mt-1 text-[11px] font-medium text-slate-400 uppercase tracking-tight">
                    <span>ROE: <span className="text-slate-600">{stock.fundamentals.roe?.toFixed(1)}%</span></span>
                    <span>P/E: <span className="text-slate-600">{stock.fundamentals.pe?.toFixed(1)}</span></span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-slate-300 font-bold uppercase mb-1">Score</div>
                  <div className="text-2xl font-black text-blue-600 leading-none">
                    {stock.buffettScore}
                  </div>
                </div>
              </div>
            ))
          ) : !isRanking && (
            <div className="py-20 text-center bg-white rounded-3xl border border-dashed border-slate-200">
              <Shield className="mx-auto text-slate-200 mb-4" size={48} />
              <p className="text-slate-400 font-medium">點擊按鈕獲取最新評分</p>
            </div>
          )}
        </div>

        <footer className="mt-12 mb-8 text-center text-slate-300 text-xs font-medium uppercase tracking-[0.2em]">
          Data Powered by Yahoo Finance
        </footer>
      </div>
    </div>
  );
}

export default App;
