import { useState, useEffect } from 'react';
import { useData } from '../context/DataContext';
import * as api from '../utils/api';
import { formatCurrency, formatPercent, getScoreColor, formatDateTime } from '../utils/formatting';

const Opportunities = () => {
  const { fetchOpportunities } = useData();
  const [opportunities, setOpportunities] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState({
    min_score: 50,
    opportunity_type: '',
    is_active: true,
  });

  useEffect(() => {
    loadOpportunities();
  }, [filter]);

  const loadOpportunities = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const params = {};
      if (filter.min_score !== null && filter.min_score !== undefined) params.min_score = filter.min_score;
      if (filter.opportunity_type) params.opportunity_type = filter.opportunity_type;
      if (filter.is_active !== undefined) params.is_active = filter.is_active;

      const data = await api.getOpportunities(params);
      setOpportunities(data);
    } catch (error) {
      console.error('Error loading opportunities:', error);
      setError('Failed to load opportunities. Please check your connection and try again.');
      setOpportunities([]); // Ensure empty state on error
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setIsScanning(true);
      // Trigger opportunity scan
      await api.scanOpportunities();
      // Wait a bit for the scan to process
      await new Promise(resolve => setTimeout(resolve, 2000));
      // Reload opportunities
      await loadOpportunities();
    } catch (error) {
      console.error('Error scanning opportunities:', error);
    } finally {
      setIsScanning(false);
    }
  };

  const opportunityTypes = [
    { value: '', label: 'All Types' },
    { value: 'premium_sell', label: 'Premium Sell (Credit)' },
    { value: 'premium_buy', label: 'Premium Buy (Debit)' },
    { value: 'gamma_scalp', label: 'Gamma Scalping' },
    { value: 'overpriced', label: 'Overpriced' },
    { value: 'underpriced', label: 'Underpriced' },
    { value: 'high_delta', label: 'High Delta' },
    { value: 'high_iv', label: 'High IV' },
    { value: 'low_iv', label: 'Low IV' },
    { value: 'unusual_volume', label: 'Unusual Volume' },
    { value: 'high_time_value', label: 'High Time Value' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
          Trading Opportunities
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Automated detection of mispriced options and trading setups
        </p>
      </div>

      {/* Filters */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Filters
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Minimum Score
            </label>
            <input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={filter.min_score}
              onChange={(e) => setFilter({ ...filter, min_score: e.target.value === '' ? 0 : parseFloat(e.target.value) })}
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Opportunity Type
            </label>
            <select
              value={filter.opportunity_type}
              onChange={(e) => setFilter({ ...filter, opportunity_type: e.target.value })}
              className="input-field"
            >
              {opportunityTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Status
            </label>
            <select
              value={filter.is_active.toString()}
              onChange={(e) => setFilter({ ...filter, is_active: e.target.value === 'true' })}
              className="input-field"
            >
              <option value="true">Active Only</option>
              <option value="false">Inactive Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Opportunities List */}
      <div className="card">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
            {isLoading ? 'Loading...' : `${opportunities.length} Opportunities Found`}
          </h3>
          <button
            onClick={handleRefresh}
            disabled={isScanning || isLoading}
            className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isScanning ? '⏳ Scanning...' : '🔄 Refresh'}
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded-lg">
            <p className="font-semibold">Error</p>
            <p>{error}</p>
          </div>
        )}

        {isLoading ? (
          <div className="text-center text-gray-600 dark:text-gray-400 py-12">
            <p className="text-lg">Loading opportunities...</p>
          </div>
        ) : opportunities.length > 0 ? (
          <div className="space-y-4">
            {opportunities.map((opp) => (
              <div
                key={opp.id}
                className="p-6 bg-gray-50 dark:bg-gray-700 rounded-lg hover:shadow-lg transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-3">
                      <div
                        className={`px-4 py-2 rounded-full text-white text-lg font-bold ${getScoreColor(
                          opp.score
                        )}`}
                      >
                        {opp.score.toFixed(0)}
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-gray-900 dark:text-white">
                          {opp.opportunity_type.replace('_', ' ').toUpperCase()}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {formatDateTime(opp.timestamp)}
                        </div>
                      </div>
                    </div>

                    <p className="text-gray-700 dark:text-gray-300 mb-2">
                      {opp.description}
                    </p>

                    {opp.contract && (
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        Contract: {opp.contract.contract_symbol} |
                        Strike: {formatCurrency(opp.contract.strike_price)} |
                        Expiry: {formatDateTime(opp.contract.expiry_date)}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col space-y-2">
                    <span
                      className={`px-3 py-1 rounded text-xs font-semibold ${
                        opp.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {opp.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-600 dark:text-gray-400 py-12">
            <p className="text-lg">No opportunities found</p>
            <p className="text-sm mt-2">
              Try adjusting your filters or adding more symbols to your watchlist
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Opportunities;
