import React, { useState, useEffect } from 'react';
import { TrendingUp, RefreshCw, Award, DollarSign, Activity, Shield, Zap, AlertCircle } from 'lucide-react';

// 模擬數據
const MOCK_DATA = {
  top25: {
    status: "success",
    total_analyzed: 69,
    last_update: new Date().toISOString(),
    rankings: [
      {
        symbol: "NVDA",
        companyName: "NVIDIA Corporation",
        sector: "科技股",
        buffettScore: 92.5,
        currentPrice: 875.28,
        momentum: 45.2,
        totalRisk: 42.5,
        roe: 28.5,
        pe: 62.3,
        recommendation: "強力推薦 ⭐⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 75, quality: 95, momentum: 92, growth: 98 },
        risks: { debt: 15.2, valuation: 65.8, volatility: 45.3 },
        buffettCriteria: { grade: "A+", criteria_passed: 4 }
      },
      {
        symbol: "MSFT",
        companyName: "Microsoft Corporation",
        sector: "科技股",
        buffettScore: 88.3,
        currentPrice: 420.55,
        momentum: 32.8,
        totalRisk: 28.3,
        roe: 42.3,
        pe: 35.2,
        recommendation: "強力推薦 ⭐⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 82, quality: 98, momentum: 85, growth: 88 },
        risks: { debt: 12.5, valuation: 42.8, volatility: 25.6 },
        buffettCriteria: { grade: "A+", criteria_passed: 5 }
      },
      {
        symbol: "AAPL",
        companyName: "Apple Inc.",
        sector: "科技股",
        buffettScore: 86.7,
        currentPrice: 185.92,
        momentum: 28.5,
        totalRisk: 25.8,
        roe: 147.4,
        pe: 29.8,
        recommendation: "強力推薦 ⭐⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 85, quality: 100, momentum: 82, growth: 75 },
        risks: { debt: 18.3, valuation: 38.5, volatility: 22.4 },
        buffettCriteria: { grade: "A+", criteria_passed: 4 }
      },
      {
        symbol: "META",
        companyName: "Meta Platforms Inc.",
        sector: "科技股",
        buffettScore: 84.2,
        currentPrice: 512.33,
        momentum: 156.8,
        totalRisk: 35.2,
        roe: 32.8,
        pe: 26.5,
        recommendation: "強力推薦 ⭐⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 88, quality: 92, momentum: 95, growth: 82 },
        risks: { debt: 8.5, valuation: 44.2, volatility: 38.5 },
        buffettCriteria: { grade: "A", criteria_passed: 4 }
      },
      {
        symbol: "JPM",
        companyName: "JPMorgan Chase & Co.",
        sector: "金融股",
        buffettScore: 82.5,
        currentPrice: 215.44,
        momentum: 42.3,
        totalRisk: 32.5,
        roe: 18.2,
        pe: 12.8,
        recommendation: "優質標的 ⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 95, quality: 85, momentum: 88, growth: 65 },
        risks: { debt: 35.8, valuation: 28.5, volatility: 32.8 },
        buffettCriteria: { grade: "A", criteria_passed: 4 }
      },
      {
        symbol: "V",
        companyName: "Visa Inc.",
        sector: "金融股",
        buffettScore: 81.8,
        currentPrice: 285.67,
        momentum: 25.5,
        totalRisk: 22.8,
        roe: 45.2,
        pe: 32.5,
        recommendation: "優質標的 ⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 82, quality: 95, momentum: 78, growth: 75 },
        risks: { debt: 15.2, valuation: 42.5, volatility: 18.5 },
        buffettCriteria: { grade: "A", criteria_passed: 4 }
      },
      {
        symbol: "MA",
        companyName: "Mastercard Inc.",
        sector: "金融股",
        buffettScore: 80.5,
        currentPrice: 475.22,
        momentum: 28.8,
        totalRisk: 24.5,
        roe: 152.8,
        pe: 38.5,
        recommendation: "優質標的 ⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 78, quality: 100, momentum: 82, growth: 72 },
        risks: { debt: 12.5, valuation: 48.2, volatility: 19.8 },
        buffettCriteria: { grade: "A", criteria_passed: 3 }
      },
      {
        symbol: "WMT",
        companyName: "Walmart Inc.",
        sector: "民生消費股",
        buffettScore: 78.3,
        currentPrice: 72.85,
        momentum: 18.5,
        totalRisk: 18.5,
        roe: 22.5,
        pe: 28.5,
        recommendation: "優質標的 ⭐⭐",
        marketPhase: "多頭排列",
        factors: { value: 82, quality: 88, momentum: 72, growth: 68 },
        risks: { debt: 22.5, valuation: 38.5, volatility: 12.8 },
        buffettCriteria: { grade: "B", criteria_passed: 3 }
      }
    ],
    statistics: {
      average_score: 81.8,
      average_risk: 28.8,
      high_grade_stocks: 18,
      sector_distribution: { "科技股": 12, "金融股": 8, "民生消費股": 5 },
      count: 25
    }
  },
  sectors: [
    {
      sector: "科技股",
      description: "科技創新類股票",
      total_stocks: 23,
      analyzed_stocks: 23,
      average_score: 79.5,
      average_risk: 35.2,
      sector_risk: "中風險",
      top_picks: [
        {
          symbol: "NVDA",
          companyName: "NVIDIA Corporation",
          sector: "科技股",
          buffettScore: 92.5,
          currentPrice: 875.28,
          momentum: 45.2,
          totalRisk: 42.5,
          roe: 28.5,
          pe: 62.3,
          recommendation: "強力推薦 ⭐⭐⭐",
          marketPhase: "多頭排列",
          factors: { value: 75, quality: 95, momentum: 92, growth: 98 },
          buffettCriteria: { grade: "A+", criteria_passed: 4 }
        },
        {
          symbol: "MSFT",
          companyName: "Microsoft Corporation",
          sector: "科技股",
          buffettScore: 88.3,
          currentPrice: 420.55,
          momentum: 32.8,
          totalRisk: 28.3,
          roe: 42.3,
          pe: 35.2,
          recommendation: "強力推薦 ⭐⭐⭐",
          marketPhase: "多頭排列",
          factors: { value: 82, quality: 98, momentum: 85, growth: 88 },
          buffettCriteria: { grade: "A+", criteria_passed: 5 }
        }
      ]
    },
    {
      sector: "金融股",
      description: "銀行、保險與金融服務",
      total_stocks: 23,
      analyzed_stocks: 23,
      average_score: 75.2,
      average_risk: 28.5,
      sector_risk: "低風險",
      top_picks: [
        {
          symbol: "JPM",
          companyName: "JPMorgan Chase & Co.",
          sector: "金融股",
          buffettScore: 82.5,
          currentPrice: 215.44,
          momentum: 42.3,
          totalRisk: 32.5,
          roe: 18.2,
          pe: 12.8,
          recommendation: "優質標的 ⭐⭐",
          marketPhase: "多頭排列",
          factors: { value: 95, quality: 85, momentum: 88, growth: 65 },
          buffettCriteria: { grade: "A", criteria_passed: 4 }
        }
      ]
    },
    {
      sector: "民生消費股",
      description: "日常消費與零售",
      total_stocks: 23,
      analyzed_stocks: 23,
      average_score: 72.8,
      average_risk: 22.5,
      sector_risk: "低風險",
      top_picks: [
        {
          symbol: "WMT",
          companyName: "Walmart Inc.",
          sector: "民生消費股",
          buffettScore: 78.3,
          currentPrice: 72.85,
          momentum: 18.5,
          totalRisk: 18.5,
          roe: 22.5,
          pe: 28.5,
          recommendation: "優質標的 ⭐⭐",
          marketPhase: "多頭排列",
          factors: { value: 82, quality: 88, momentum: 72, growth: 68 },
          buffettCriteria: { grade: "B", criteria_passed: 3 }
        }
      ]
    }
  ]
};

const BuffettStockPicker = () => {
  const [activeTab, setActiveTab] = useState('top25');
  const [top25Data, setTop25Data] = useState(null);
  const [sectorsData, setSectorsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [selectedSector, setSelectedSector] = useState(null);
  const [useRealAPI, setUseRealAPI] = useState(false);

  const API_BASE = 'https://buffett-analyzer.onrender.com';

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      if (useRealAPI) {
        // 嘗試連接真實 API
        const [top25Res, sectorsRes] = await Promise.all([
          fetch(`${API_BASE}/sp500-analysis`),
          fetch(`${API_BASE}/api/stock-pool`)
        ]);

        if (!top25Res.ok || !sectorsRes.ok) {
          throw new Error('無法連接到後端服務');
        }

        const top25 = await top25Res.json();
        const sectors = await sectorsRes.json();

        setTop25Data(top25);
        setSectorsData(sectors);
        setLastUpdate(new Date(top25.last_update));
      } else {
        // 使用模擬數據
        setTimeout(() => {
          setTop25Data(MOCK_DATA.top25);
          setSectorsData(MOCK_DATA.sectors);
          setLastUpdate(new Date(MOCK_DATA.top25.last_update));
          setLoading(false);
        }, 500);
        return;
      }
      
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [useRealAPI]);

  const handleRefresh = async () => {
    if (useRealAPI) {
      try {
        setLoading(true);
        await fetch(`${API_BASE}/api/refresh`, { method: 'POST' });
        setTimeout(() => fetchData(), 3000);
      } catch (err) {
        setError('刷新失敗');
        setLoading(false);
      }
    } else {
      fetchData();
    }
  };

  const getScoreColor = (score) => {
    if (score >= 85) return 'bg-green-100 text-green-800';
    if (score >= 70) return 'bg-blue-100 text-blue-800';
    if (score >= 55) return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-800';
  };

  const GradeBadge = ({ grade }) => {
    const colors = {
      'A+': 'bg-purple-600',
      'A': 'bg-green-600',
      'B': 'bg-blue-600',
      'C': 'bg-gray-600'
    };
    return (
      <span className={`${colors[grade] || colors.C} text-white px-2 py-1 rounded text-xs font-bold`}>
        {grade}
      </span>
    );
  };

  const StockCard = ({ stock, rank }) => (
    <div className="bg-white rounded-lg shadow border border-gray-200 p-4 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            {rank && (
              <span className={`text-lg font-bold ${rank <= 3 ? 'text-yellow-500' : 'text-gray-400'}`}>
                #{rank}
              </span>
            )}
            <h3 className="font-bold text-lg">{stock.symbol}</h3>
            <GradeBadge grade={stock.buffettCriteria?.grade} />
          </div>
          <p className="text-sm text-gray-600 mb-1">{stock.companyName}</p>
          <span className="text-xs px-2 py-1 bg-gray-100 rounded">{stock.sector}</span>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold px-3 py-2 rounded ${getScoreColor(stock.buffettScore)}`}>
            {stock.buffettScore.toFixed(1)}
          </div>
          <p className="text-xs text-gray-500 mt-1">評分</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-gray-50 p-2 rounded">
          <div className="flex items-center gap-1 mb-1">
            <DollarSign className="w-4 h-4 text-gray-600" />
            <span className="text-xs text-gray-600">價格</span>
          </div>
          <p className="font-semibold">${stock.currentPrice.toFixed(2)}</p>
        </div>
        <div className="bg-gray-50 p-2 rounded">
          <div className="flex items-center gap-1 mb-1">
            <Activity className="w-4 h-4 text-gray-600" />
            <span className="text-xs text-gray-600">年動能</span>
          </div>
          <p className={`font-semibold ${stock.momentum >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {stock.momentum > 0 ? '+' : ''}{stock.momentum.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-3 text-center">
        <div className="bg-blue-50 p-2 rounded">
          <p className="text-xs text-blue-600">價值</p>
          <p className="font-bold text-blue-700">{stock.factors?.value || 0}</p>
        </div>
        <div className="bg-green-50 p-2 rounded">
          <p className="text-xs text-green-600">品質</p>
          <p className="font-bold text-green-700">{stock.factors?.quality || 0}</p>
        </div>
        <div className="bg-purple-50 p-2 rounded">
          <p className="text-xs text-purple-600">動能</p>
          <p className="font-bold text-purple-700">{stock.factors?.momentum || 0}</p>
        </div>
        <div className="bg-orange-50 p-2 rounded">
          <p className="text-xs text-orange-600">成長</p>
          <p className="font-bold text-orange-700">{stock.factors?.growth || 0}</p>
        </div>
      </div>

      <div className="flex justify-between text-sm border-t pt-2">
        <div className="flex items-center gap-1">
          <Shield className="w-4 h-4" />
          <span>風險: {stock.totalRisk.toFixed(1)}%</span>
        </div>
        <div>ROE: {stock.roe.toFixed(1)}%</div>
        <div>P/E: {stock.pe === 'N/A' ? 'N/A' : stock.pe.toFixed(1)}</div>
      </div>

      <div className="mt-2 pt-2 border-t text-sm">
        {stock.recommendation.includes('⭐⭐⭐') && <Award className="w-4 h-4 text-yellow-500 inline mr-1" />}
        <span className="font-medium">{stock.recommendation}</span>
      </div>
    </div>
  );

  const SectorCard = ({ sector }) => (
    <div 
      className="bg-white rounded-lg shadow border p-4 cursor-pointer hover:shadow-lg transition-shadow"
      onClick={() => setSelectedSector(sector)}
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-bold text-lg">{sector.sector}</h3>
          <p className="text-sm text-gray-600">{sector.description}</p>
        </div>
        <Zap className="w-5 h-5 text-blue-500" />
      </div>
      
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-blue-50 p-2 rounded">
          <p className="text-xs text-blue-600">平均評分</p>
          <p className="text-xl font-bold text-blue-700">{sector.average_score.toFixed(1)}</p>
        </div>
        <div className="bg-purple-50 p-2 rounded">
          <p className="text-xs text-purple-600">平均風險</p>
          <p className="text-xl font-bold text-purple-700">{sector.average_risk.toFixed(1)}%</p>
        </div>
      </div>

      <div className="flex justify-between text-sm text-gray-600">
        <span>已分析: {sector.analyzed_stocks}/{sector.total_stocks}</span>
        <span className="font-semibold">{sector.sector_risk}</span>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">載入數據中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2 text-center">載入失敗</h2>
          <p className="text-gray-600 text-center mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 mb-2"
          >
            重試
          </button>
          <button
            onClick={() => {
              setUseRealAPI(false);
              setError(null);
              fetchData();
            }}
            className="w-full bg-gray-600 text-white py-2 rounded-lg hover:bg-gray-700"
          >
            使用示範數據
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      <div className="bg-white shadow border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <TrendingUp className="w-7 h-7 text-blue-600" />
                巴菲特選股系統
              </h1>
              {lastUpdate && (
                <p className="text-sm text-gray-500 mt-1">
                  更新: {lastUpdate.toLocaleString('zh-TW')}
                  {!useRealAPI && <span className="ml-2 text-blue-600">(示範模式)</span>}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setUseRealAPI(!useRealAPI)}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 text-sm"
              >
                {useRealAPI ? '示範模式' : '真實 API'}
              </button>
              <button
                onClick={handleRefresh}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                <RefreshCw className="w-4 h-4" />
                刷新
              </button>
            </div>
          </div>
        </div>
      </div>

      {top25Data && (
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
              <p className="text-sm text-gray-600">總分析</p>
              <p className="text-2xl font-bold">{top25Data.total_analyzed}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
              <p className="text-sm text-gray-600">平均評分</p>
              <p className="text-2xl font-bold">{top25Data.statistics?.average_score.toFixed(1)}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-purple-500">
              <p className="text-sm text-gray-600">優質股票</p>
              <p className="text-2xl font-bold">{top25Data.statistics?.high_grade_stocks}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-orange-500">
              <p className="text-sm text-gray-600">平均風險</p>
              <p className="text-2xl font-bold">{top25Data.statistics?.average_risk.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 mb-6">
        <div className="bg-white rounded-lg shadow p-1 inline-flex gap-1">
          <button
            onClick={() => setActiveTab('top25')}
            className={`px-6 py-2 rounded font-medium ${
              activeTab === 'top25'
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            TOP 25
          </button>
          <button
            onClick={() => setActiveTab('sectors')}
            className={`px-6 py-2 rounded font-medium ${
              activeTab === 'sectors'
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            產業分類
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 pb-8">
        {activeTab === 'top25' && top25Data && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {top25Data.rankings?.map((stock, index) => (
              <StockCard key={stock.symbol} stock={stock} rank={index + 1} />
            ))}
          </div>
        )}

        {activeTab === 'sectors' && (
          <div>
            {!selectedSector ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {sectorsData.map((sector) => (
                  <SectorCard key={sector.sector} sector={sector} />
                ))}
              </div>
            ) : (
              <div>
                <button
                  onClick={() => setSelectedSector(null)}
                  className="mb-4 text-blue-600 hover:text-blue-700 font-medium"
                >
                  ← 返回
                </button>
                <h2 className="text-2xl font-bold mb-4">
                  {selectedSector.sector} - {selectedSector.description}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {selectedSector.top_picks?.map((stock, index) => (
                    <StockCard key={stock.symbol} stock={stock} rank={index + 1} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BuffettStockPicker;
