import React, { useState } from 'react';
import { TrendingUp, Activity, Clock, ShieldAlert, BarChart3, AlertCircle } from 'lucide-react';

// 請替換為你真實的 Render 後端網址
const API_BASE_URL = "https://buffett-analyzer.onrender.com";

const App = () => {
  const [rankings, setRankings] = useState([]);
  const [isRanking, setIsRanking] = useState(false);
  const [lastUpdateTime, setLastUpdateTime] = useState(null);

  const startAnalysis = async () => {
    setIsRanking(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/sp500-analysis`);
      if (!response.ok) throw new Error(`伺服器錯誤: ${response.status}`);
      const data = await response.json();
      
      if (data.status === "success") {
        setRankings(data.rankings);
        setLastUpdateTime(data.last_updated);
      } else {
        alert("數據獲取失敗: " + data.message);
      }
    } catch (error) {
      console.error("Error:", error);
      alert("連線失敗！Render 伺服器若正在喚醒，請稍等一分鐘後再試。");
    } finally {
      setIsRanking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-10 text-center">
        <h1 className="text-4xl font-black text-slate-900 mb-4 flex items-center justify-center gap-3">
          <TrendingUp className="text-blue-600 w-10 h-10" />
          巴菲特量化分析系統
        </h1>
        <p className="text-slate-500 text-lg mb-8">
          多因子評分模型 × 全自動風險掃描
        </p>
        
        <button
          onClick={startAnalysis}
          disabled={isRanking}
          className={`px-10 py-4 rounded-full font-bold text-xl shadow-2xl transition-all flex items-center gap-3 mx-auto ${
            isRanking 
              ? 'bg-slate-400 cursor-not-allowed text-white' 
              : 'bg-blue-600 hover:bg-blue-700 text-white hover:scale-105 active:scale-95'
          }`}
        >
          {isRanking ? (
            <><div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div> 分析中...</>
          ) : '獲取 S&P 500 深度報告'}
        </button>
        
        {lastUpdateTime && (
          <div className="mt-4 flex items-center justify-center gap-2 text-sm text-slate-400">
            <Clock size={14} /> 資料更新時間：{lastUpdateTime}
          </div>
        )}
      </div>

      {/* Rankings Grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {rankings.map((stock, index) => (
          <div key={stock.symbol} className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden flex flex-col">
            {/* Top Bar: Rank & Score */}
            <div className="bg-slate-900 p-4 flex justify-between items-center text-white">
              <span className="text-2xl font-black opacity-50">#{index + 1}</span>
              <div className="text-right">
                <div className="text-xs opacity-60 uppercase tracking-widest">Buffett Score</div>
                <div className="text-3xl font-black text-blue-400">{stock.buffettScore.toFixed(1)}</div>
              </div>
            </div>

            <div className="p-6 flex-grow">
              {/* Symbol & Price */}
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-3xl font-bold text-slate-800">{stock.symbol}</h2>
                  <div className="flex gap-2 mt-1">
                    <span className="text-xs font-bold px-2 py-0.5 bg-blue-50 text-blue-600 rounded">S&P 500</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${stock.totalRisk > 50 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
                      {stock.totalRisk > 50 ? '高風險警告' : '風險穩健'}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-slate-700">${stock.currentPrice}</div>
                  <div className={`text-sm font-bold ${stock.momentum >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                    {stock.momentum > 0 ? '↑' : '↓'} {Math.abs(stock.momentum).toFixed(1)}% (1Y)
                  </div>
                </div>
              </div>

              {/* 1. 多因子展示區 (Factors) */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3 text-slate-800 font-bold">
                  <BarChart3 size={18} className="text-blue-600" /> 多因子表現
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(stock.factors).map(([key, val]) => (
                    <div key={key} className="bg-slate-50 p-2 rounded-xl border border-slate-100">
                      <div className="flex justify-between text-[10px] text-slate-400 uppercase font-bold mb-1">
                        <span>{key === 'value' ? '價值' : key === 'quality' ? '質量' : key === 'momentum' ? '動能' : '成長'}</span>
                        <span>{val.toFixed(0)}</span>
                      </div>
                      <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500" style={{ width: `${val}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 2. 風險儀表板 (Risks) */}
              <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                <div className="flex items-center gap-2 mb-3 text-slate-800 font-bold">
                  <ShieldAlert size={18} className="text-rose-500" /> 風險成分分析
                </div>
                <div className="space-y-3">
                  {/* 總風險進度條 */}
                  <div>
                    <div className="flex justify-between text-xs mb-1 font-bold text-slate-600">
                      <span>綜合風險指數</span>
                      <span>{stock.totalRisk.toFixed(1)}%</span>
                    </div>
                    <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                      <div 
                        className={`h-full transition-all duration-1000 ${stock.totalRisk > 50 ? 'bg-rose-500' : 'bg-emerald-500'}`}
                        style={{ width: `${stock.totalRisk}%` }}
                      />
                    </div>
                  </div>
                  {/* 風險細分 */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="text-center">
                      <div className="text-[9px] text-slate-400 font-bold uppercase">債務</div>
                      <div className={`text-xs font-black ${stock.risks.debt > 60 ? 'text-rose-500' : 'text-slate-600'}`}>{stock.risks.debt.toFixed(0)}%</div>
                    </div>
                    <div className="text-center border-x border-slate-200">
                      <div className="text-[9px] text-slate-400 font-bold uppercase">估值</div>
                      <div className={`text-xs font-black ${stock.risks.valuation > 60 ? 'text-rose-500' : 'text-slate-600'}`}>{stock.risks.valuation.toFixed(0)}%</div>
                    </div>
                    <div className="text-center">
                      <div className="text-[9px] text-slate-400 font-bold uppercase">波動</div>
                      <div className={`text-xs font-black ${stock.risks.volatility > 60 ? 'text-rose-500' : 'text-slate-600'}`}>{stock.risks.volatility.toFixed(0)}%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Footer Data */}
            <div className="p-4 bg-slate-50 border-t border-slate-100 grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-[10px] text-slate-400 font-bold">ROE</div>
                <div className="text-sm font-black text-slate-700">{stock.roe.toFixed(1)}%</div>
              </div>
              <div className="text-center">
                <div className="text-[10px] text-slate-400 font-bold">Forward PE</div>
                <div className="text-sm font-black text-slate-700">{stock.pe > 0 ? stock.pe.toFixed(1) : 'N/A'}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {!isRanking && rankings.length === 0 && (
        <div className="text-center py-32">
          <div className="bg-white w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
            <Activity size={40} className="text-slate-300" />
          </div>
          <h3 className="text-xl font-bold text-slate-400">準備就緒</h3>
          <p className="text-slate-400">點擊上方按鈕，開啟深度量化分析</p>
        </div>
      )}
    </div>
  );
};

export default App;
