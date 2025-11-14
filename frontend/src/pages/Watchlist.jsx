import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useData } from '../context/DataContext';
import { formatDate } from '../utils/formatting';

const Watchlist = () => {
  const { watchlist, addToWatchlist, removeFromWatchlist, triggerUpdate } = useData();
  const [newSymbol, setNewSymbol] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [adding, setAdding] = useState(false);

  const handleAddSymbol = async (e) => {
    e.preventDefault();

    if (!newSymbol.trim()) return;

    setAdding(true);
    const success = await addToWatchlist(newSymbol.trim().toUpperCase(), companyName.trim() || null);

    if (success) {
      setNewSymbol('');
      setCompanyName('');
    }

    setAdding(false);
  };

  const handleRemoveSymbol = async (symbol) => {
    if (window.confirm(`Remove ${symbol} from watchlist?`)) {
      await removeFromWatchlist(symbol);
    }
  };

  const handleUpdateSymbol = async (symbol) => {
    await triggerUpdate(symbol);
    alert(`Data update scheduled for ${symbol}`);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
          Watchlist
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Manage your tracked symbols and monitor their options
        </p>
      </div>

      {/* Add Symbol Form */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Add New Symbol
        </h3>

        <form onSubmit={handleAddSymbol} className="flex flex-col md:flex-row gap-4">
          <input
            type="text"
            placeholder="Symbol (e.g., AAPL)"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            className="input-field flex-1"
            required
          />

          <input
            type="text"
            placeholder="Company Name (optional)"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="input-field flex-1"
          />

          <button
            type="submit"
            disabled={adding}
            className="btn-primary whitespace-nowrap"
          >
            {adding ? 'Adding...' : '➕ Add Symbol'}
          </button>
        </form>
      </div>

      {/* Watchlist Table */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Your Watchlist ({watchlist.length})
        </h3>

        {watchlist.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    Symbol
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    Company
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    Added
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {watchlist.map((symbol) => (
                  <tr key={symbol.id} className="table-row">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link
                        to={`/symbol/${symbol.symbol}`}
                        className="text-blue-600 hover:text-blue-800 font-semibold text-lg"
                      >
                        {symbol.symbol}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {symbol.company_name}
                      </div>
                      {symbol.sector && (
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {symbol.sector}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(symbol.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                      <Link
                        to={`/options/${symbol.symbol}`}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        Options
                      </Link>
                      <button
                        onClick={() => handleUpdateSymbol(symbol.symbol)}
                        className="text-green-600 hover:text-green-800"
                      >
                        Update
                      </button>
                      <button
                        onClick={() => handleRemoveSymbol(symbol.symbol)}
                        className="text-red-600 hover:text-red-800"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-600 dark:text-gray-400 py-12">
            <p className="text-lg">Your watchlist is empty</p>
            <p className="text-sm mt-2">Add symbols above to start tracking options</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Watchlist;
