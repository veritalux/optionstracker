import { format, parseISO } from 'date-fns';

export const formatCurrency = (value, decimals = 2) => {
  if (value === null || value === undefined) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

export const formatPercent = (value, decimals = 2) => {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(decimals)}%`;
};

export const formatNumber = (value, decimals = 2) => {
  if (value === null || value === undefined) return 'N/A';
  return value.toFixed(decimals);
};

export const formatVolume = (volume) => {
  if (!volume) return '0';
  if (volume >= 1000000) {
    return `${(volume / 1000000).toFixed(1)}M`;
  } else if (volume >= 1000) {
    return `${(volume / 1000).toFixed(1)}K`;
  }
  return volume.toString();
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
    return format(date, 'MMM dd, yyyy');
  } catch (error) {
    return 'Invalid Date';
  }
};

export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
    return format(date, 'MMM dd, yyyy HH:mm');
  } catch (error) {
    return 'Invalid Date';
  }
};

export const getColorForValue = (value, inverse = false) => {
  if (value === null || value === undefined) return 'text-gray-500';

  if (inverse) {
    return value > 0 ? 'text-red-600' : 'text-green-600';
  }

  return value > 0 ? 'text-green-600' : 'text-red-600';
};

export const getScoreColor = (score) => {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-blue-500';
  if (score >= 40) return 'bg-yellow-500';
  return 'bg-red-500';
};

export const getIVRankColor = (ivRank) => {
  if (ivRank >= 80) return 'text-red-600 font-bold';
  if (ivRank >= 60) return 'text-orange-600';
  if (ivRank >= 40) return 'text-yellow-600';
  if (ivRank >= 20) return 'text-green-600';
  return 'text-green-700 font-bold';
};
