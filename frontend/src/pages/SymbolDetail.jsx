import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import * as api from '../utils/api';
import {
  formatCurrency,
  formatPercent,
  formatDate,
  formatVolume,
  getColorForValue,
  getIVRankColor,
} from '../utils/formatting';

const SymbolDetail = () => {
  const { symbol } = useParams();
  const [symbolData, setSymbolData] = useState(null);
  const [stockPrices, setStockPrices] = useState([]);
  const [ivAnalysis, setIVAnalysis] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSymbolData();
  }, [symbol]);

  const loadSymbolData = async () => {
    setLoading(true);
    try {
      const [symbolInfo, prices, iv, opps] = await Promise.all([
        api.getSymbol(symbol),
        api.getStockPrices(symbol, { limit: 30 }),
        api.getIVAnalysis(symbol, 30),
        api.getSymbolOpportunities(symbol, true),
      ]);

      setSymbolData(symbolInfo);
      setStockPrices(prices);
      setIVAnalysis(iv);
      setOpportunities(opps);
    } catch (error) {
      console.error('Error loading symbol data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600 dark:text-gray-400">Loading symbol data...</div>
      </div>
    );
  }

  if (!symbolData) {
    return (
      <div className="text-center text-gray-600 dark:text-gray-400 py-12">
        <p className="text-lg">Symbol not found</p>
      </div>
    );
  }

  const currentPrice = stockPrices.length > 0 ? stockPrices[0].close_price : null;
  const previousPrice = stockPrices.length > 1 ? stockPrices[1].close_price : null;
  const priceChange = currentPrice && previousPrice ? currentPrice - previousPrice : 0;
  const priceChangePercent = previousPrice ? (priceChange / previousPrice) * 100 : 0;

  const latestIV = ivAnalysis.length > 0 ? ivAnalysis[0] : null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center space-x-4">
            <h2 className="text-4xl font-bold text-gray-900 dark:text-white">
              {symbol}
            </h2>
            {currentPrice && (
              <div className="text-3xl font-semibold text-gray-900 dark:text-white">
                {formatCurrency(currentPrice)}
              </div>
            )}
            {priceChange !== 0 && (
              <div className={`text-xl font-semibold ${getColorForValue(priceChange)}`}>
                {priceChange > 0 ? '+' : ''}
                {formatCurrency(priceChange)} ({priceChangePercent.toFixed(2)}%)
              </div>
            )}
          </div>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            {symbolData.company_name}
          </p>
          {symbolData.sector && (
            <p className="text-sm text-gray-500 dark:text-gray-500">
              {symbolData.sector}
            </p>
          )}
        </div>

        <Link to={`/options/${symbol}`} className="btn-primary">
          View Options Chain →
        </Link>
      </div>

      {/* IV Analysis */}
      {latestIV && (
        <div className="card">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Implied Volatility Analysis
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                Current IV
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatPercent(latestIV.current_iv * 100)}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                IV Rank
              </div>
              <div className={`text-2xl font-bold ${getIVRankColor(latestIV.iv_rank)}`}>
                {formatPercent(latestIV.iv_rank)}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                IV Percentile
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatPercent(latestIV.iv_percentile)}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                HV (30d)
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {latestIV.hv_30d ? formatPercent(latestIV.hv_30d * 100) : 'N/A'}
              </div>
            </div>
          </div>

          <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
            <p>
              <strong>IV Rank:</strong> Shows where current IV sits in the 52-week range (0-100%).
              High IV Rank (&gt;80%) suggests expensive options. Low IV Rank (&lt;20%) suggests cheap options.
            </p>
          </div>
        </div>
      )}

      {/* Opportunities */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Active Opportunities ({opportunities.length})
        </h3>

        {opportunities.length > 0 ? (
          <div className="space-y-3">
            {opportunities.slice(0, 5).map((opp) => (
              <div
                key={opp.id}
                className="p-4 bg-gray-50 dark:bg-gray-700 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded">
                        {opp.opportunity_type.replace('_', ' ').toUpperCase()}
                      </span>
                      <span className="text-lg font-bold text-gray-900 dark:text-white">
                        Score: {opp.score.toFixed(0)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      {opp.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {opportunities.length > 5 && (
              <Link
                to="/opportunities"
                className="block text-center text-blue-600 hover:text-blue-800 font-medium"
              >
                View all {opportunities.length} opportunities →
              </Link>
            )}
          </div>
        ) : (
          <div className="text-center text-gray-600 dark:text-gray-400 py-8">
            No active opportunities for this symbol
          </div>
        )}
      </div>

      {/* Recent Price History */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Recent Price History
        </h3>

        {stockPrices.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Date
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Open
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    High
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Low
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Close
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Volume
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {stockPrices.slice(0, 10).map((price) => (
                  <tr key={price.id} className="table-row">
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                      {formatDate(price.timestamp)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900 dark:text-white">
                      {formatCurrency(price.open_price)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-green-600">
                      {formatCurrency(price.high_price)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-red-600">
                      {formatCurrency(price.low_price)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right font-semibold text-gray-900 dark:text-white">
                      {formatCurrency(price.close_price)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-600 dark:text-gray-400">
                      {formatVolume(price.volume)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-600 dark:text-gray-400 py-8">
            No price data available
          </div>
        )}
      </div>
    </div>
  );
};

export default SymbolDetail;
