import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import * as api from '../utils/api';
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  formatDate,
  formatVolume,
  getColorForValue,
} from '../utils/formatting';

const OptionsChain = () => {
  const { symbol } = useParams();
  const [symbolData, setSymbolData] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [optionType, setOptionType] = useState('all');
  const [loading, setLoading] = useState(true);
  const [contractsWithPrices, setContractsWithPrices] = useState([]);

  useEffect(() => {
    loadData();
  }, [symbol]);

  useEffect(() => {
    if (contracts.length > 0 && selectedExpiry) {
      loadContractsWithPrices();
    }
  }, [selectedExpiry, optionType, contracts]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [symbolInfo, allContracts] = await Promise.all([
        api.getSymbol(symbol),
        api.getOptionContracts(symbol),
      ]);

      setSymbolData(symbolInfo);
      setContracts(allContracts);

      // Auto-select first expiry date
      if (allContracts.length > 0) {
        const expiryDates = [...new Set(allContracts.map((c) => c.expiry_date))].sort();
        if (expiryDates.length > 0) {
          setSelectedExpiry(expiryDates[0]);
        }
      }
    } catch (error) {
      console.error('Error loading options data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadContractsWithPrices = async () => {
    setLoading(true);
    try {
      // Filter contracts by selected expiry and option type
      let filtered = contracts.filter((c) => c.expiry_date === selectedExpiry);

      if (optionType !== 'all') {
        filtered = filtered.filter((c) => c.option_type === optionType);
      }

      // Load latest price for each contract
      const contractsWithPriceData = await Promise.all(
        filtered.map(async (contract) => {
          try {
            const prices = await api.getOptionPrices(contract.id, { limit: 1 });
            const latestPrice = prices && prices.length > 0 ? prices[0] : null;
            return {
              contract,
              priceData: latestPrice,
              timestamp: latestPrice ? new Date(latestPrice.timestamp) : null,
            };
          } catch (error) {
            console.error(`Error loading price for contract ${contract.id}:`, error);
            return {
              contract,
              priceData: null,
              timestamp: null,
            };
          }
        })
      );

      // Sort by timestamp (most recent first), then by strike price
      contractsWithPriceData.sort((a, b) => {
        if (a.timestamp && b.timestamp) {
          return b.timestamp - a.timestamp; // Most recent first
        }
        if (a.timestamp && !b.timestamp) return -1;
        if (!a.timestamp && b.timestamp) return 1;
        // Fallback to strike price if no timestamps
        return a.contract.strike_price - b.contract.strike_price;
      });

      setContractsWithPrices(contractsWithPriceData);
    } catch (error) {
      console.error('Error loading contracts with prices:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600 dark:text-gray-400">Loading options chain...</div>
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

  // Get unique expiry dates
  const expiryDates = [...new Set(contracts.map((c) => c.expiry_date))].sort();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
            Options Chain: {symbol}
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            {symbolData.company_name}
          </p>
        </div>

        <Link to={`/symbol/${symbol}`} className="btn-secondary">
          ← Back to Symbol
        </Link>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Expiration Date
            </label>
            <select
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              className="input-field"
            >
              {expiryDates.map((date) => (
                <option key={date} value={date}>
                  {formatDate(date)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Option Type
            </label>
            <select
              value={optionType}
              onChange={(e) => setOptionType(e.target.value)}
              className="input-field"
            >
              <option value="all">All</option>
              <option value="call">Calls</option>
              <option value="put">Puts</option>
            </select>
          </div>
        </div>
      </div>

      {/* Options Table */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          {contractsWithPrices.length} Contracts (sorted by latest update)
        </h3>

        {contractsWithPrices.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Type
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Strike
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Expiry
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Last Updated
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Last Price
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Bid/Ask
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Volume
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    OI
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    IV
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Delta
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">
                    Theta
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {contractsWithPrices.map((item) => (
                  <ContractRow
                    key={item.contract.id}
                    contract={item.contract}
                    priceData={item.priceData}
                    timestamp={item.timestamp}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-600 dark:text-gray-400 py-12">
            <p className="text-lg">No options contracts found</p>
            <p className="text-sm mt-2">
              Try selecting a different expiration date or option type
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const ContractRow = ({ contract, priceData, timestamp }) => {
  if (!priceData) {
    return (
      <tr className="table-row">
        <td colSpan="11" className="px-3 py-3 text-center text-sm text-gray-500">
          No price data available
        </td>
      </tr>
    );
  }

  // Format timestamp for display
  const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(ts);
  };

  return (
    <tr className="table-row">
      <td className="px-3 py-3 whitespace-nowrap">
        <span
          className={`px-2 py-1 text-xs font-semibold rounded ${
            contract.option_type === 'call'
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          {contract.option_type.toUpperCase()}
        </span>
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right font-semibold text-gray-900 dark:text-white">
        {formatCurrency(contract.strike_price)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-600 dark:text-gray-400">
        {priceData.expiry_date ? formatDate(priceData.expiry_date) : formatDate(contract.expiry_date)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-600 dark:text-gray-400">
        {formatTimestamp(timestamp)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right text-gray-900 dark:text-white">
        {formatCurrency(priceData.last_price)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right text-sm text-gray-600 dark:text-gray-400">
        {formatCurrency(priceData.bid)} / {formatCurrency(priceData.ask)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right text-gray-900 dark:text-white">
        {formatVolume(priceData.volume)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right text-gray-600 dark:text-gray-400">
        {formatVolume(priceData.open_interest)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap text-right text-gray-900 dark:text-white">
        {priceData.implied_volatility
          ? formatPercent(priceData.implied_volatility * 100)
          : 'N/A'}
      </td>
      <td
        className={`px-3 py-3 whitespace-nowrap text-right font-semibold ${getColorForValue(
          priceData.delta
        )}`}
      >
        {priceData.delta ? formatNumber(priceData.delta, 3) : 'N/A'}
      </td>
      <td
        className={`px-3 py-3 whitespace-nowrap text-right ${getColorForValue(
          priceData.theta,
          true
        )}`}
      >
        {priceData.theta ? formatNumber(priceData.theta, 3) : 'N/A'}
      </td>
    </tr>
  );
};

export default OptionsChain;
