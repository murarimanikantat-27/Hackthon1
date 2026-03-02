// API Configuration
export const API_BASE_URL = '';

// API Endpoints
export const API_ENDPOINTS = {
  incidents: `${API_BASE_URL}/api/incidents`,
  incidentDetail: (id) => `${API_BASE_URL}/api/incidents/${id}`,
  stats: `${API_BASE_URL}/api/dashboard/stats`,
  remediate: (id) => `${API_BASE_URL}/api/incidents/${id}/remediate`,
};
