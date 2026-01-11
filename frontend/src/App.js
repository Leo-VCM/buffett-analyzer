import React, { useState } from 'react';
import { TrendingUp, Activity, Clock } from 'lucide-react';

// 請確保這裡填寫你正確的 Render 後端網址
const API_BASE_URL = "https://buffett-analyzer.onrender.com";

const App = () => {
  const [rankings, setRankings] = useState([]);
  const [isRanking, setIsRanking] = useState(false);
  const [lastUpdateTime, setLastUpdateTime] = useState(null);

  // 輔助函式：根據分數給予評等標籤
  const getRecommendation = (score) => {
    if (score >= 80) return { text: "強力推薦", bg: "bg-emerald-100", color: "text-emerald-700" };
    if (score >= 60) return { text: "值得關注", bg: "bg-blue-100", color: "text-blue-700" };
    return { text: "觀望", bg: "bg-slate-100", color: "text-slate-700" };
  };

  const startAnalysis = async () => {
    setIsRanking(true);
    try {
      console.log("正在請求 S&P 500 分析數據...");
      const response = await fetch(`${API_BASE_URL}/api/sp500-analysis`);
      
      if (!response.ok) throw new Error(`伺服器錯誤: ${response.status}`);

      const data = await response.json();
      
      if (data.status === "success" && data.rankings) {
        setRankings(data.rankings);
        setLastUpdateTime(data.last_updated);
      } else {
        alert("數據獲取失敗: " + (data.message || "未知原因"));
      }
    } catch (error) {
      console.error("Analysis Error:", error);
      alert("連線超時或失敗！\n\n提示：Render 伺服器若正在喚醒，首次分析約需 45-60 秒，請稍後再試。");
    } finally {
      setIsRanking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-12 text-center">
        <h1 className="text-4xl font-bold text-slate-900 mb-4 flex items-center justify-center gap-3">
          <TrendingUp className="text-blue-600 w-10 h-10" />
          巴菲特選股：S&P 500 即時排名
        </h1>
        <p className="text-slate-600 max-w-2xl mx-auto mb-8">
          結合價值 (PE/PB)、質量 (ROE) 與動能因子。
          <br />
          <span className="text-sm font-medium text-blue-500">※ 每日自動更新快取，第二次查詢秒開</span>
        </p>
        
        <div className="flex flex-col items-center gap-4">
          <button
            onClick={startAnalysis}
            disabled={isRanking}
            className={`px-8 py-4 rounded-full font-bold text-lg shadow-xl transition-all flex items-center gap-2 ${
              isRanking 
                ? 'bg-slate-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700 text-white hover:scale-105 active:scale-95'
            }`}
          >
            {isRanking ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                伺服器計算中 (約 45 秒)...
              </>
            ) : (
              '開始即時分析 S&P 500 前 50 強'
            )}
          </button>
          
          {lastUpdateTime && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Clock size={14} />
              最後更新時間：{lastUpdateTime}
            </div>
          )}
        </div>
      </div>

      {/* Rankings Grid */}
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {rankings.map((stock, index) => {
          const rec = getRecommendation(stock.buffettScore);
          return (
            <div 
              key={stock.symbol}
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 hover:shadow-md transition-shadow relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 bg-blue-600 text-white px-4 py-1 rounded-bl-xl font-bold">
                #{index + 1}
              </div>

              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 font-bold text-xl">
                  {stock.symbol[0]}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">{stock.symbol}</h3>
                  <span className={`text-sm font-medium px-2 py-0.5 rounded ${rec.bg} ${rec.color}`}>
                    {rec.text}
                  </span>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-end">
                  <span className="text-slate-500 text-sm">巴菲特總分</span>
                  <span className="text-3xl font-black text-blue-600">{stock.buffettScore}</span>
                </div>
                
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-600 rounded-full transition-all duration-1000"
                    style={{ width: `${stock.buffettScore}%` }}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4 mt-6">
                  <div className="bg-slate-50 p-3 rounded-xl text-center">
                    <div className="text-slate-400 text-xs mb-1">ROE</div>
                    <div className="font-bold text-slate-700">{stock.roe?.toFixed(1)}%</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl text-center">
                    <div className="text-slate-400 text-xs mb-1">預估 PE</div>
                    <div className="font-bold text-slate-700">{stock.pe > 0 ? stock.pe.toFixed(1) : 'N/A'}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl text-center">
                    <div className="text-slate-400 text-xs mb-1">股價</div>
                    <div className="font-bold text-slate-700">${stock.currentPrice?.toFixed(1)}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl text-center">
                    <div className="text-slate-400 text-xs mb-1">12M 動能</div>
                    <div className={`font-bold ${stock.momentum >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {stock.momentum > 0 ? '+' : ''}{stock.momentum?.toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {!isRanking && rankings.length === 0 && (
        <div className="text-center py-20 opacity-40">
          <Activity size={64} className="mx-auto mb-4" />
          <p>點擊上方按鈕，開始分析真實市場數據</p>
        </div>
      )}
    </div>
  );
};

export default App;
