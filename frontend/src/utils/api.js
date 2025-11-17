import axios from 'axios';

// Use environment variable for API URL, fallback to local development
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Symbols / Watchlist
export const getSymbols = async (isActive = true) => {
  const response = await api.get(`/symbols`, {
    params: { is_active: isActive }
  });
  return response.data;
};

export const getSymbol = async (symbol) => {
  const response = await api.get(`/symbols/${symbol}`);
  return response.data;
};

export const addSymbol = async (symbolData) => {
  const response = await api.post(`/symbols`, symbolData);
  return response.data;
};

export const deleteSymbol = async (symbol) => {
  const response = await api.delete(`/symbols/${symbol}`);
  return response.data;
};

// Stock Prices
export const getStockPrices = async (symbol, params = {}) => {
  const response = await api.get(`/symbols/${symbol}/prices`, { params });
  return response.data;
};

// Options
export const getOptionContracts = async (symbol, params = {}) => {
  const response = await api.get(`/symbols/${symbol}/options`, { params });
  return response.data;
};

export const getOptionPrices = async (contractId, params = {}) => {
  const response = await api.get(`/options/${contractId}/prices`, { params });
  return response.data;
};

// IV Analysis
export const getIVAnalysis = async (symbol, limit = 30) => {
  const response = await api.get(`/symbols/${symbol}/iv-analysis`, {
    params: { limit }
  });
  return response.data;
};

// Opportunities
export const getOpportunities = async (params = {}) => {
  const response = await api.get(`/opportunities`, { params });
  return response.data;
};

export const getSymbolOpportunities = async (symbol, isActive = true) => {
  const response = await api.get(`/symbols/${symbol}/opportunities`, {
    params: { is_active: isActive }
  });
  return response.data;
};

export const scanOpportunities = async () => {
  const response = await api.post(`/opportunities/scan`);
  return response.data;
};

// Dashboard
export const getDashboardSummary = async () => {
  const response = await api.get(`/dashboard`);
  return response.data;
};

// Data Updates
export const updateSymbolData = async (symbol) => {
  const response = await api.post(`/update/${symbol}`);
  return response.data;
};

export const updateAllSymbols = async () => {
  const response = await api.post(`/update-all`);
  return response.data;
};

export default api;
