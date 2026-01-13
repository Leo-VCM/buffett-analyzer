import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, Clock, ShieldAlert, BarChart3, Mail, Lock, Unlock, ChevronRight } from 'lucide-react';

const API_BASE_URL = "https://buffett-analyzer.onrender.com";

// 模擬昨天的舊數據 (當用戶未登入時顯示)
const MOCK_YESTERDAY_DATA = [
  {
    symbol: "AAPL",
    companyName: "Apple Inc.",
    buffettScore: 82.5,
    currentPrice: 185.92,
    momentum: 12.4,
    totalRisk: 35.2,
    roe: 154.2,
    pe: 28.5,
    factors: { value: 60, quality: 95, momentum: 70, growth: 80 },
    risks: { debt: 20, valuation: 60, volatility: 25 }
  },
  {
    symbol: "MSFT",
    companyName: "Microsoft Corp.",
    buffettScore: 79.1,
    currentPrice: 398.45,
    momentum: 15.8,
    totalRisk: 30.1,
    roe: 38.5,
    pe: 35.2,
    factors: { value: 50, quality: 90, momentum: 85, growth: 75 },
    risks: { debt: 15, valuation: 70, volatility: 20 }
  }
];

const App = () => {
  const [rankings, setRankings] = useState(MOCK_YESTERDAY_DATA);
  const [isRanking, setIsRanking] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [email, setEmail] = useState("");
  const [isLive, setIsLive] = useState(false); // 標記目前是否為真實數據

  // 處理登入/註冊
  const handleLogin = (e) => {
    e.preventDefault();
    if (email.includes("@")) {
      setIsLoggedIn(true);
      // 登入後自動執行一次真實數據抓取
      fetchRealTimeData();
    }
  };

  // 向後端索取今天真實數據
  const fetchRealTimeData = async () => {
    if (!isLoggedIn && isLive) return;
    setIsRanking(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/batch-analyze?symbols=AAPL,MSFT,TSLA,GOOGL,AMZN`);
      const data = await response.json();
      setRankings(data);
      setIsLive(true);
    } catch (error) {
      alert("即時數據獲取失敗，請確認後端已啟動。");
    } finally {
      setIsRanking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Navbar */}
      <nav className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center shadow-sm">
        <div className="flex items-center gap-2 font-black text-xl text-slate-800">
          <TrendingUp className="text-blue-600" /> BUFFETT AI
        </div>
        <div className="flex items-center gap-4">
          {isLoggedIn ? (
            <span className="flex items-center gap-2 text-emerald-600 font-bold bg-emerald-50 px-4 py-2 rounded-full text-sm">
              <Unlock size={16} /> VIP 會員已連線
            </span>
          ) : (
            <span className="text-slate-400 text-sm flex items-center gap-1">
              <Lock size={16} /> 訪客模式 (僅限舊數據)
            </span>
          )}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 md:p-12">
        {/* Header Section */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-black text-slate-900 mb-6 tracking-tight">
            巴菲特量化 <span className="text-blue-600">即時分析系統</span>
          </h1>
          
          {!isLoggedIn ? (
            <div className="bg-blue-600 rounded-3xl p-8 text-white max-w-2xl mx-auto shadow-2xl transform transition hover:scale-[1.02]">
              <h3 className="text-2xl font-bold mb-2">想要查看今日真實數據？</h3>
              <p className="opacity-80 mb-6">輸入信箱立即免費解鎖 S&P 500 即時評分報告</p>
              <form onSubmit={handleLogin} className="flex flex-col md:flex-row gap-3">
                <input 
                  type="email" 
                  placeholder="your-email@example.com"
                  className="flex-grow px-6 py-4 rounded-2xl text-slate-900 outline-none"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
                <button type="submit" className="bg-slate-900 px-8 py-4 rounded-2xl font-bold hover:bg-black transition-colors flex items-center justify-center gap-2">
                  立即解鎖 <ChevronRight size={20} />
                </button>
              </form>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <div className="text-emerald-500 font-bold flex items-center gap-2 bg-emerald-50 px-6 py-3 rounded-2xl border border-emerald-100">
                <Activity className="animate-pulse" /> 數據監控中：目前顯示為 2026 即時行情
              </div>
              <button 
                onClick={fetchRealTimeData}
                disabled={isRanking}
                className="bg-blue-600 text-white px-10 py-4 rounded-full font-bold shadow-xl hover:bg-blue-700 transition-all disabled:bg-slate-300"
              >
                {isRanking ? "刷新中..." : "重新掃描市場"}
              </button>
            </div>
          )}
        </div>

        {/* 數據看板 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {rankings.map((stock, index) => (
            <div key={stock.symbol} className={`bg-white rounded-[2rem] shadow-xl border border-slate-100 overflow-hidden relative ${!isLoggedIn && 'opacity-70 blur-[0.5px]'}`}>
              {/* 未登入遮罩效果 */}
              {!isLoggedIn && index > 1 && (
                <div className="absolute inset-0 z-10 bg-white/40 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center">
                  <Lock size={40} className="text-slate-400 mb-2" />
                  <p className="font-bold text-slate-600">註冊會員解鎖更多股票</p>
                </div>
              )}

              <div className="bg-slate-900 p-5 flex justify-between items-center text-white">
                <span className="font-black opacity-30">RANK {index + 1}</span>
                <div className="text-right">
                  <span className="text-3xl font-black text-blue-400">{stock.buffettScore}</span>
                </div>
              </div>

              <div className="p-8">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-3xl font-black text-slate-800 leading-none">{stock.symbol}</h2>
                    <p className="text-slate-400 text-sm mt-2">{stock.companyName}</p>
                  </div>
                  <div className="text-right text-2xl font-bold text-slate-700">
                    ${stock.currentPrice}
                  </div>
                </div>

                {/* 多因子雷達數據展示 */}
                <div className="space-y-4">
                   <div className="flex items-center gap-2 font-bold text-slate-700 text-sm">
                      <BarChart3 size={16} className="text-blue-600"/> 核心因子評分
                   </div>
                   <div className="grid grid-cols-2 gap-2">
                      {Object.entries(stock.factors).map(([k, v]) => (
                        <div key={k} className="bg-slate-50 p-3 rounded-2xl border border-slate-100">
                           <div className="text-[10px] text-slate-400 uppercase font-bold">{k}</div>
                           <div className="text-lg font-black text-slate-700">{v}</div>
                        </div>
                      ))}
                   </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default App;
