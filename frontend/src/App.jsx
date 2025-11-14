import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { DataProvider } from './context/DataContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Watchlist from './pages/Watchlist';
import OptionsChain from './pages/OptionsChain';
import Opportunities from './pages/Opportunities';
import SymbolDetail from './pages/SymbolDetail';

function App() {
  return (
    <DataProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/opportunities" element={<Opportunities />} />
            <Route path="/symbol/:symbol" element={<SymbolDetail />} />
            <Route path="/options/:symbol" element={<OptionsChain />} />
          </Routes>
        </Layout>
      </Router>
    </DataProvider>
  );
}

export default App;
