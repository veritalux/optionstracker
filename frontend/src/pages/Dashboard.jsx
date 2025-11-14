import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useData } from '../context/DataContext';
import { formatCurrency, formatPercent, getScoreColor } from '../utils/formatting';

const Dashboard = () => {
  const { dashboardData, opportunities, fetchDashboardData, fetchOpportunities, triggerUpdate, loading } = useData();

  useEffect(() => {
    fetchDashboardData();
    fetchOpportunities({ is_active: true, limit: 10 });
  }, []);

  const handleRefreshData = async () => {
    // Trigger backend update for all symbols
    await triggerUpdate();

    // Wait a moment for backend to process, then refresh frontend data
    setTimeout(() => {
      fetchDashboardData();
      fetchOpportunities({ is_active: true, limit: 10 });
    }, 2000);
  };

  if (!dashboardData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600 dark:text-gray-400">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white">
          Morning Dashboard
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          {new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="stat-card">
          <div className="stat-value">{dashboardData.symbol_count || 0}</div>
          <div className="stat-label">Symbols Tracked</div>
        </div>

        <div className="stat-card bg-gradient-to-br from-green-500 to-green-600">
          <div className="stat-value">{dashboardData.opportunity_count || 0}</div>
          <div className="stat-label">Active Opportunities</div>
        </div>

        <div className="stat-card bg-gradient-to-br from-purple-500 to-purple-600">
          <div className="stat-value">
            {dashboardData.hot_symbols?.length || 0}
          </div>
          <div className="stat-label">Hot Symbols</div>
        </div>
      </div>

      {/* Top Opportunities */}
      <div className="card">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
            Top Opportunities
          </h3>
          <Link
            to="/opportunities"
            className="text-blue-600 hover:text-blue-800 font-medium"
          >
            View All →
          </Link>
        </div>

        <div className="space-y-4">
          {opportunities && opportunities.length > 0 ? (
            opportunities.slice(0, 5).map((opp) => (
              <div
                key={opp.id}
                className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition"
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <div
                      className={`px-3 py-1 rounded-full text-white text-sm font-semibold ${getScoreColor(
                        opp.score
                      )}`}
                    >
                      {opp.score.toFixed(0)}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 dark:text-white">
                        {opp.opportunity_type.replace('_', ' ').toUpperCase()}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        {opp.description}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center text-gray-600 dark:text-gray-400 py-8">
              No opportunities found. Add symbols to your watchlist to get started.
            </div>
          )}
        </div>
      </div>

      {/* Hot Symbols */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Hot Symbols (Most Opportunities)
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {dashboardData.hot_symbols && dashboardData.hot_symbols.length > 0 ? (
            dashboardData.hot_symbols.map((symbol) => (
              <Link
                key={symbol.symbol}
                to={`/symbol/${symbol.symbol}`}
                className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-gray-700 dark:to-gray-600 rounded-lg hover:shadow-lg transition"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white">
                      {symbol.symbol}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {symbol.company_name}
                    </div>
                  </div>
                  <div className="bg-blue-600 text-white rounded-full w-8 h-8 flex items-center justify-center font-bold">
                    {symbol.opportunity_count}
                  </div>
                </div>
              </Link>
            ))
          ) : (
            <div className="col-span-3 text-center text-gray-600 dark:text-gray-400 py-8">
              No active symbols with opportunities
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/watchlist" className="btn-primary text-center">
            📝 Manage Watchlist
          </Link>
          <Link to="/opportunities" className="btn-primary text-center">
            💡 Browse Opportunities
          </Link>
          <button
            onClick={handleRefreshData}
            disabled={loading}
            className="btn-secondary text-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '⏳ Updating...' : '🔄 Refresh Data'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
