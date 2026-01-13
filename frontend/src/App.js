import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, Clock, ShieldAlert, BarChart3, Mail, Lock, Unlock, ChevronRight, Download, AlertCircle, Loader2 } from 'lucide-react';

const API_BASE_URL = "https://buffett-analyzer.onrender.com";

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
  },
  {
    symbol: "GOOGL",
    companyName: "Alphabet Inc.",
    buffettScore: 76.8,
    currentPrice: 142.30,
    momentum: 10.2,
    totalRisk: 28.5,
    roe: 29.8,
    pe: 24.1,
    factors: { value: 65, quality: 85, momentum: 60, growth: 90 },
    risks: { debt: 10, valuation: 50, volatility: 30 }
  },
  {
    symbol: "AMZN",
    companyName: "Amazon.com Inc.",
    buffettScore: 74.2,
    currentPrice: 178.55,
    momentum: 18.5,
    totalRisk: 42.1,
    roe: 21.3,
    pe: 58.2,
    factors: { value: 40, quality: 80, momentum: 95, growth: 85 },
    risks: { debt: 25, valuation: 80, volatility: 40 }
  },
  {
    symbol: "TSLA",
    companyName: "Tesla Inc.",
    buffettScore: 68.5,
    currentPrice: 248.92,
    momentum: 25.8,
    totalRisk: 65.3,
    roe: 18.9,
    pe: 75.4,
    factors: { value: 30, quality: 70, momentum: 100, growth: 95 },
    risks: { debt: 35, valuation: 95, volatility: 80 }
  }
];

const App = () => {
  const [rankings, setRankings] = useState(MOCK_YESTERDAY_DATA);
  const [isRanking, setIsRanking] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [email, setEmail] = useState("");
  const [isLive, setIsLive] = useState(false);
  const [lastUpdateTime, setLastUpdateTime] = useState("2026-01-12 15:30:00");
  const [error, setError] = useState(null);
  const [serverWaking, setServerWaking] = useState(false);

  // 初始化時檢查是否有緩存的登入狀態
  useEffect(() => {
    // 在真實環境中，這裡會從 localStorage 讀取
    // 但在 Claude artifacts 中，我們使用 state 管理
    const savedEmail = ""; // localStorage.getItem('userEmail')
    if (savedEmail) {
      setEmail(savedEmail);
      setIsLoggedIn(true);
    }
  }, []);

  // 驗證數據格式並計算總風險
  const validateStockData = (data) => {
    if (!Array.isArray(data)) {
      throw new Error("數據格式錯誤：預期為陣列");
    }
    
    return data.map(stock => {
      // 從後端的 risks 物件計算總風險（平均值）
      const risks = stock.risks || { debt: 0, valuation: 0, volatility: 0 };
      const totalRisk = (risks.debt + risks.valuation + risks.volatility) / 3;
      
      // 從 details 提取 ROE（後端回傳在 details.roe）
      const roe = stock.details?.roe || 0;
      
      // PE 需要從 factors 推算（或後端補充）
      const pe = stock.details?.pe || 0;

      return {
        symbol: stock.symbol || "N/A",
        companyName: stock.companyName || "Unknown Company",
        buffettScore: stock.buffettScore || stock.finalScore || 0,
        currentPrice: stock.currentPrice || 0,
        momentum: stock.momentum || 0,
        totalRisk: totalRisk,
        roe: roe,
        pe: pe,
        marketPhase: stock.marketPhase || "未知",
        recommendation: stock.recommendation || "觀察",
        factors: stock.factors || { value: 0, quality: 0, momentum: 0, growth: 0 },
        risks: risks
      };
    });
  };

  // 處理登入
  const handleLogin = () => {
    if (email.includes("@")) {
      setIsLoggedIn(true);
      // 在真實環境中: localStorage.setItem('userEmail', email);
      fetchRealTimeData();
    }
  };

  // 獲取即時數據
  const fetchRealTimeData = async () => {
    setIsRanking(true);
    setError(null);
    setServerWaking(true);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/batch-analyze?symbols=AAPL,MSFT,TSLA,GOOGL,AMZN`, {
        signal: AbortSignal.timeout(90000) // 90秒超時
      });
      
      if (!response.ok) {
        throw new Error(`伺服器回應錯誤: ${response.status}`);
      }
      
      const data = await response.json();
      const validatedData = validateStockData(data);
      
      setRankings(validatedData);
      setIsLive(true);
      setLastUpdateTime(new Date().toLocaleString('zh-TW', { 
        timeZone: 'Asia/Taipei',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }));
      
      // 在真實環境中: localStorage.setItem('cachedRankings', JSON.stringify(validatedData));
      // localStorage.setItem('lastUpdateTime', lastUpdateTime);
      
    } catch (error) {
      console.error("數據獲取失敗:", error);
      setError(error.message || "無法連接到伺服器，請稍後再試");
      setIsLive(false);
    } finally {
      setIsRanking(false);
      setServerWaking(false);
    }
  };

  // 導出CSV
  const exportToCSV = () => {
    const headers = ['排名', '代號', '公司名稱', '巴菲特評分', '股價', '動能', '風險', 'ROE', 'P/E'];
    const rows = rankings.map((stock, index) => [
      index + 1,
      stock.symbol,
      stock.companyName,
      stock.buffettScore,
      stock.currentPrice,
      stock.momentum,
      stock.totalRisk,
      stock.roe,
      stock.pe
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `buffett_analysis_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  // 風險等級顏色
  const getRiskColor = (risk) => {
    if (risk < 30) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (risk < 50) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  // 風險等級文字
  const getRiskLabel = (risk) => {
    if (risk < 30) return '低風險';
    if (risk < 50) return '中風險';
    return '高風險';
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
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 text-emerald-600 font-bold bg-emerald-50 px-4 py-2 rounded-full text-sm">
                <Unlock size={16} /> {email}
              </span>
              <button 
                onClick={exportToCSV}
                className="flex items-center gap-2 bg-slate-800 text-white px-4 py-2 rounded-full text-sm hover:bg-slate-900 transition"
              >
                <Download size={16} /> 導出報告
              </button>
            </div>
          ) : (
            <span className="text-slate-400 text-sm flex items-center gap-1">
              <Lock size={16} /> 訪客模式
            </span>
          )}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 md:p-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-black text-slate-900 mb-6 tracking-tight">
            巴菲特量化 <span className="text-blue-600">即時分析系統</span>
          </h1>
          
          {/* 數據時間戳 */}
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold mb-6 ${
            isLive ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600 border border-slate-200'
          }`}>
            <Clock size={16} />
            {isLive ? '即時數據' : '歷史數據'} · 更新於 {lastUpdateTime}
          </div>
          
          {!isLoggedIn ? (
            <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-3xl p-8 text-white max-w-2xl mx-auto shadow-2xl">
              <h3 className="text-2xl font-bold mb-2">解鎖今日即時市場數據</h3>
              <p className="opacity-90 mb-6">輸入信箱免費查看 S&P 500 完整評分報告</p>
              <div className="flex flex-col md:flex-row gap-3">
                <input 
                  type="email" 
                  placeholder="your-email@example.com"
                  className="flex-grow px-6 py-4 rounded-2xl text-slate-900 outline-none focus:ring-4 focus:ring-blue-300"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                />
                <button 
                  onClick={handleLogin}
                  disabled={!email.includes("@")}
                  className="bg-slate-900 px-8 py-4 rounded-2xl font-bold hover:bg-black transition-all flex items-center justify-center gap-2 disabled:bg-slate-600 disabled:cursor-not-allowed"
                >
                  立即解鎖 <ChevronRight size={20} />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              {serverWaking && (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 px-6 py-3 rounded-2xl flex items-center gap-2 text-sm">
                  <Loader2 className="animate-spin" size={16} />
                  伺服器喚醒中，首次請求可能需要 60 秒...
                </div>
              )}
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-3 rounded-2xl flex items-center gap-2 text-sm max-w-2xl">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
              
              <button 
                onClick={fetchRealTimeData}
                disabled={isRanking}
                className="bg-blue-600 text-white px-10 py-4 rounded-full font-bold shadow-xl hover:bg-blue-700 transition-all disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isRanking ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    刷新中...
                  </>
                ) : (
                  <>
                    <Activity size={20} />
                    重新掃描市場
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* 股票卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {isRanking && !rankings.length ? (
            // 骨架屏
            [...Array(5)].map((_, i) => (
              <div key={i} className="bg-white rounded-[2rem] shadow-xl border border-slate-100 overflow-hidden animate-pulse">
                <div className="bg-slate-200 h-20"></div>
                <div className="p-8 space-y-4">
                  <div className="h-8 bg-slate-200 rounded"></div>
                  <div className="h-4 bg-slate-100 rounded w-2/3"></div>
                  <div className="grid grid-cols-2 gap-2 mt-6">
                    {[...Array(4)].map((_, j) => (
                      <div key={j} className="h-16 bg-slate-100 rounded-2xl"></div>
                    ))}
                  </div>
                </div>
              </div>
            ))
          ) : (
            rankings.map((stock, index) => (
              <div key={stock.symbol} className={`bg-white rounded-[2rem] shadow-xl border border-slate-100 overflow-hidden relative transition-all hover:shadow-2xl ${
                !isLoggedIn && index > 1 ? 'opacity-70 blur-[0.5px]' : ''
              }`}>
                {!isLoggedIn && index > 1 && (
                  <div className="absolute inset-0 z-10 bg-white/50 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center">
                    <Lock size={40} className="text-slate-400 mb-2" />
                    <p className="font-bold text-slate-600">註冊會員解鎖更多股票</p>
                  </div>
                )}

                <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-5 flex justify-between items-center text-white">
                  <span className="font-black opacity-40 text-sm">#{index + 1}</span>
                  <div className="text-right">
                    <div className="text-xs opacity-60 mb-1">巴菲特評分</div>
                    <span className="text-3xl font-black text-blue-400">{stock.buffettScore?.toFixed(1) || 'N/A'}</span>
                  </div>
                </div>

                <div className="p-8">
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <h2 className="text-3xl font-black text-slate-800 leading-none">{stock.symbol}</h2>
                      <p className="text-slate-400 text-sm mt-2">{stock.companyName}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-700">
                        ${stock.currentPrice?.toFixed(2) || 'N/A'}
                      </div>
                      <div className={`text-xs font-bold mt-1 ${stock.momentum > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {stock.momentum > 0 ? '↑' : '↓'} {Math.abs(stock.momentum || 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* 風險標籤 */}
                  <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold border mb-4 ${getRiskColor(stock.totalRisk || 0)}`}>
                    <ShieldAlert size={12} />
                    {getRiskLabel(stock.totalRisk || 0)} ({(stock.totalRisk || 0).toFixed(1)})
                  </div>

                  {/* 核心因子 */}
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 font-bold text-slate-700 text-sm">
                      <BarChart3 size={16} className="text-blue-600"/> 核心因子評分
                    </div>
                    <div className="space-y-3">
                      {Object.entries(stock.factors || {}).map(([key, value]) => (
                        <div key={key}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-500 uppercase font-bold">{key}</span>
                            <span className="text-slate-700 font-bold">{value}/100</span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                            <div 
                              className="bg-gradient-to-r from-blue-500 to-blue-600 h-full rounded-full transition-all duration-500"
                              style={{ width: `${Math.min(value || 0, 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 基本面數據 */}
                  <div className="grid grid-cols-2 gap-3 mt-6 pt-6 border-t border-slate-100">
                    <div className="bg-slate-50 p-3 rounded-xl">
                      <div className="text-xs text-slate-400 font-bold">ROE</div>
                      <div className="text-lg font-black text-slate-700">{(stock.roe || 0).toFixed(1)}%</div>
                    </div>
                    <div className="bg-slate-50 p-3 rounded-xl">
                      <div className="text-xs text-slate-400 font-bold">P/E</div>
                      <div className="text-lg font-black text-slate-700">{(stock.pe || 0).toFixed(1)}</div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
