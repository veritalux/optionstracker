import React, { createContext, useContext, useState, useEffect } from 'react';
import * as api from '../utils/api';

const DataContext = createContext();

export const useData = () => {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
};

export const DataProvider = ({ children }) => {
  const [watchlist, setWatchlist] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch watchlist
  const fetchWatchlist = async () => {
    try {
      setLoading(true);
      const data = await api.getSymbols(true);
      setWatchlist(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch watchlist');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch dashboard summary
  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const data = await api.getDashboardSummary();
      setDashboardData(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch opportunities
  const fetchOpportunities = async (params = {}) => {
    try {
      setLoading(true);
      const data = await api.getOpportunities(params);
      setOpportunities(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch opportunities');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Add symbol to watchlist
  const addToWatchlist = async (symbol, companyName = null) => {
    try {
      setLoading(true);
      await api.addSymbol({ symbol, company_name: companyName });
      await fetchWatchlist();
      setError(null);
      return true;
    } catch (err) {
      setError('Failed to add symbol');
      console.error(err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Remove symbol from watchlist
  const removeFromWatchlist = async (symbol) => {
    try {
      setLoading(true);
      await api.deleteSymbol(symbol);
      await fetchWatchlist();
      setError(null);
      return true;
    } catch (err) {
      setError('Failed to remove symbol');
      console.error(err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Trigger data update
  const triggerUpdate = async (symbol = null) => {
    try {
      setLoading(true);
      if (symbol) {
        await api.updateSymbolData(symbol);
      } else {
        await api.updateAllSymbols();
      }
      setError(null);
      return true;
    } catch (err) {
      setError('Failed to trigger update');
      console.error(err);
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Initial data load
  useEffect(() => {
    fetchWatchlist();
    fetchDashboardData();
    fetchOpportunities();
  }, []);

  // Refresh data periodically (every 5 minutes)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchDashboardData();
      fetchOpportunities();
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, []);

  const value = {
    watchlist,
    dashboardData,
    opportunities,
    loading,
    error,
    fetchWatchlist,
    fetchDashboardData,
    fetchOpportunities,
    addToWatchlist,
    removeFromWatchlist,
    triggerUpdate,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
};
