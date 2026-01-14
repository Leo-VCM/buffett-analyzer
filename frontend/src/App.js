import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, Clock, ShieldAlert, BarChart3, Lock, Unlock, ChevronRight, Download, AlertCircle, Loader2, Award, Building2 } from 'lucide-react';

const API_BASE_URL = "https://buffett-analyzer.onrender.com";

const App = () => {
  const [top25Stocks, setTop25Stocks] = useState([]);
  const [sectorData, setSectorData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("top25"); // top25 or sectors
  const [selectedSector, setSelectedSector] = useState("全部");
  const [statistics, setStatistics] = useState(null);

  const handleLogin = () => {
    if (email.includes("@")) {
      setIsLoggedIn(true);
      fetchTop25();
    }
  };

  const fetchTop25 = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('📡 獲取 TOP 25 股票池...');
      
      const response = await fetch(`${API_BASE_URL}/api/top-25`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(180000) // 3分鐘超時
      });
      
      if (!response.ok) {
        throw new Error(`伺服器回應錯誤: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('✅ TOP 25 數據:', data);
      
      setTop25Stocks(data.top_25_stocks || []);
      setStatistics(data.statistics);
      
    } catch (error) {
      console.error("❌ 獲取失敗:", error);
      setError(error.message || "無法連接到伺服器");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSectorData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const url = selectedSector === "全部" 
        ? `${API_BASE_URL}/api/stock-pool?limit=8`
        : `${API_BASE_URL}/api/stock-pool?sector=${selectedSector}&limit=8`;
      
      console.log('📡 獲取產業數據:', url);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(180000)
      });
      
      if (!response.ok) {
        throw new Error(`伺服器回應錯誤: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('✅ 產業數據:', data);
      
      setSectorData(data);
      
    } catch (error) {
      console.error("❌ 獲取失敗:", error);
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const exportToCSV = () => {
    const stocks = activeTab === "top25" ? top25Stocks : sectorData.flatMap(s => s.top_picks);
    const headers = ['排名', '代號', '公司', '產業', '評分', '等級', '股價', '動能', '風險', 'ROE', 'P/E', '建議'];
    const rows = stocks.map((stock, idx) => [
      idx + 1,
      stock.symbol,
      stock.companyName,
      stock.sector,
      stock.buffettScore,
      stock.buffettCriteria?.grade || 'N/A',
      stock.currentPrice,
      stock.momentum,
      stock.totalRisk,
      stock.roe,
      stock.pe,
      stock.recommendation
    ]);
    
    const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `buffett_top25_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  const getRiskColor = (risk) => {
    if (risk < 35) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (risk < 55) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const getGradeColor = (grade) => {
    if (grade === 'A+') return 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-white';
    if (grade === 'A') return 'bg-emerald-500 text-white';
    if (grade === 'B') return 'bg-amber-500 text-white';
    return 'bg-slate-500 text-white';
  };

  const getSectorIcon = (sector) => {
    if (sector === '科技股') return '💻';
    if (sector === '金融股') return '🏦';
    if (sector === '民生消費股') return '🛒';
    return '📊';
  };

  const displayStocks = activeTab === "top25" 
    ? top25Stocks 
    : sectorData.flatMap(s => s.top_picks);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <nav className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2 font-black text-xl text-slate-800">
            <Award className="text-blue-600" /> 巴菲特選股系統
          </div>
          <div className="flex items-center gap-4">
            {isLoggedIn ? (
              <>
                <span className="text-sm text-slate-600">{email}</span>
                <button onClick={exportToCSV} className="flex items-center gap-2 bg-slate-800 text-white px-4 py-2 rounded-full text-sm hover:bg-slate-900 transition">
                  <Download size={16} /> 導出報告
                </button>
              </>
            ) : (
              <span className="text-slate-400 text-sm flex items-center gap-1">
                <Lock size={16} /> 訪客模式
              </span>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto p-6 md:p-12">
        {/* Title */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-black text-slate-900 mb-4">
            巴菲特 <span className="text-blue-600">TOP 25</span> 股票池
          </h1>
          <p className="text-slate-600 text-lg mb-8">基於價值投資原則，從科技、金融、民生消費三大產業篩選優質股票</p>
          
          {!isLoggedIn ? (
            <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-3xl p-8 text-white max-w-2xl mx-auto shadow-2xl">
              <h3 className="text-2xl font-bold mb-2">解鎖巴菲特選股系統</h3>
              <p className="opacity-90 mb-6">輸入信箱查看完整 TOP 25 股票池與產業分析</p>
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
                  className="bg-slate-900 px-8 py-4 rounded-2xl font-bold hover:bg-black transition-all disabled:bg-slate-600"
                >
                  立即解鎖 <ChevronRight className="inline" size={20} />
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Tabs */}
              <div className="flex justify-center gap-4 mb-6">
                <button 
                  onClick={() => { setActiveTab("top25"); fetchTop25(); }}
                  className={`px-6 py-3 rounded-full font-bold transition ${
                    activeTab === "top25" 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  🏆 TOP 25 股票池
                </button>
                <button 
                  onClick={() => { setActiveTab("sectors"); fetchSectorData(); }}
                  className={`px-6 py-3 rounded-full font-bold transition ${
                    activeTab === "sectors" 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  📊 產業分類
                </button>
              </div>

              {/* Sector Filter */}
              {activeTab === "sectors" && (
                <div className="flex justify-center gap-3 mb-6">
                  {["全部", "科技股", "金融股", "民生消費股"].map(sector => (
                    <button
                      key={sector}
                      onClick={() => { setSelectedSector(sector); }}
                      className={`px-4 py-2 rounded-full text-sm font-bold transition ${
                        selectedSector === sector
                          ? 'bg-slate-900 text-white'
                          : 'bg-white text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {getSectorIcon(sector)} {sector}
                    </button>
                  ))}
                </div>
              )}

              {/* Statistics */}
              {statistics && activeTab === "top25" && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  <div className="bg-white p-4 rounded-2xl shadow-md">
                    <div className="text-xs text-slate-500 mb-1">平均評分</div>
                    <div className="text-2xl font-black text-blue-600">{statistics.average_score}</div>
                  </div>
                  <div className="bg-white p-4 rounded-2xl shadow-md">
                    <div className="text-xs text-slate-500 mb-1">平均風險</div>
                    <div className="text-2xl font-black text-amber-600">{statistics.average_risk}</div>
                  </div>
                  <div className="bg-white p-4 rounded-2xl shadow-md">
                    <div className="text-xs text-slate-500 mb-1">高評級股票</div>
                    <div className="text-2xl font-black text-emerald-600">{statistics.high_grade_stocks}</div>
                  </div>
                  <div className="bg-white p-4 rounded-2xl shadow-md">
                    <div className="text-xs text-slate-500 mb-1">產業分布</div>
                    <div className="text-sm font-bold text-slate-700">
                      {Object.entries(statistics.sector_distribution).map(([k, v]) => (
                        <div key={k}>{getSectorIcon(k)} {v}</div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-3 rounded-2xl mb-6">
                  <AlertCircle className="inline mr-2" size={16} />
                  {error}
                </div>
              )}

              {isLoading && (
                <div className="text-center py-12">
                  <Loader2 className="animate-spin mx-auto mb-4" size={48} />
                  <p className="text-slate-600">分析中... 這可能需要 1-2 分鐘</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Stock Cards */}
        {isLoggedIn && !isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {displayStocks.map((stock, idx) => (
              <div key={stock.symbol} className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden hover:shadow-2xl transition">
                {/* Header */}
                <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-5 text-white">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="text-xs opacity-60 mb-1">#{idx + 1}</div>
                      <div className="text-3xl font-black">{stock.symbol}</div>
                      <div className="text-xs opacity-80 mt-1">{getSectorIcon(stock.sector)} {stock.sector}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs opacity-60 mb-1">巴菲特評分</div>
                      <div className="text-3xl font-black text-blue-400">{stock.buffettScore}</div>
                      <div className={`mt-2 px-3 py-1 rounded-full text-xs font-bold ${getGradeColor(stock.buffettCriteria?.grade)}`}>
                        {stock.buffettCriteria?.grade || 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Body */}
                <div className="p-6">
                  <div className="mb-4">
                    <h3 className="font-bold text-slate-800 mb-1">{stock.companyName}</h3>
                    <div className="flex justify-between items-center">
                      <span className="text-2xl font-black text-slate-700">${stock.currentPrice?.toFixed(2)}</span>
                      <span className={`text-sm font-bold ${stock.momentum > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {stock.momentum > 0 ? '↑' : '↓'} {Math.abs(stock.momentum).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Risk Badge */}
                  <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold border mb-4 ${getRiskColor(stock.totalRisk)}`}>
                    <ShieldAlert size={12} />
                    風險值 {stock.totalRisk?.toFixed(1)}
                  </div>

                  {/* Buffett Criteria */}
                  <div className="bg-slate-50 rounded-2xl p-4 mb-4">
                    <div className="text-xs font-bold text-slate-600 mb-2">巴菲特標準檢查</div>
                    <div className="space-y-1 text-xs">
                      {stock.buffettCriteria?.details && Object.values(stock.buffettCriteria.details).map((detail, i) => (
                        <div key={i} className="text-slate-700">{detail}</div>
                      ))}
                    </div>
                  </div>

                  {/* Factors */}
                  <div className="space-y-2">
                    {Object.entries(stock.factors || {}).map(([key, value]) => (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-500 uppercase font-bold">{key}</span>
                          <span className="text-slate-700 font-bold">{value}/100</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                          <div 
                            className="bg-gradient-to-r from-blue-500 to-blue-600 h-full rounded-full"
                            style={{ width: `${Math.min(value, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Bottom Stats */}
                  <div className="grid grid-cols-2 gap-3 mt-4 pt-4 border-t">
                    <div className="bg-slate-50 p-3 rounded-xl">
                      <div className="text-xs text-slate-400 font-bold">ROE</div>
                      <div className="text-lg font-black text-slate-700">{stock.roe?.toFixed(1)}%</div>
                    </div>
                    <div className="bg-slate-50 p-3 rounded-xl">
                      <div className="text-xs text-slate-400 font-bold">P/E</div>
                      <div className="text-lg font-black text-slate-700">{stock.pe?.toFixed(1)}</div>
                    </div>
                  </div>

                  {/* Recommendation */}
                  <div className="mt-4 text-center">
                    <span className="text-sm font-bold text-blue-600">{stock.recommendation}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
