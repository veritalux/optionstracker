import { Link, useLocation } from 'react-router-dom';
import { useData } from '../context/DataContext';

const Layout = ({ children }) => {
  const location = useLocation();
  const { loading, error } = useData();

  const navigation = [
    { name: 'Dashboard', path: '/', icon: '📊' },
    { name: 'Watchlist', path: '/watchlist', icon: '👁️' },
    { name: 'Opportunities', path: '/opportunities', icon: '💡' },
  ];

  const isActive = (path) => {
    return location.pathname === path;
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                📈 Options Tracker
              </h1>
            </div>

            <nav className="flex space-x-4">
              {navigation.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-4 py-2 rounded-md font-medium transition ${
                    isActive(item.path)
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  <span className="mr-2">{item.icon}</span>
                  {item.name}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Loading Bar */}
      {loading && (
        <div className="bg-blue-500 h-1">
          <div className="animate-pulse bg-blue-600 h-full w-1/2"></div>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <strong className="font-bold">Error: </strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white dark:bg-gray-800 shadow-md mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-gray-600 dark:text-gray-400 text-sm">
            Options Tracker © 2024 | For informational purposes only. Not financial advice.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
