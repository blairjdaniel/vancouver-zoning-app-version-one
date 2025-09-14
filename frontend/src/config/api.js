// Frontend API configuration
// This will be used to determine the correct API base URL
// depending on whether we're in development or production

const getApiBaseUrl = () => {
  // In production (Docker), use relative URLs that go through nginx proxy
  if (process.env.NODE_ENV === 'production') {
    return '';  // Relative URLs like '/api/...'
  }
  
  // In development, connect directly to Flask backend
  return 'http://localhost:5002';
};

export const API_BASE_URL = getApiBaseUrl();
export const API_ENDPOINTS = {
  FETCH_PARCEL: `${API_BASE_URL}/api/fetch-parcel`,
  VALIDATE_BUILDING_UNITS: `${API_BASE_URL}/api/validate-building-units`,
  GENERATE_BUILDING_UNITS: `${API_BASE_URL}/api/generate-building-units`,
  FEW_SHOT_EXAMPLES: `${API_BASE_URL}/api/few-shot/examples`,
  HF_GENERATE_LOCAL: `${API_BASE_URL}/api/hf/generate-local`,
  GENERATION_PROGRESS: (taskId) => `${API_BASE_URL}/api/generation-progress/${taskId}`,
};

// Helper function to get full download URL
export const getDownloadUrl = (relativePath) => {
  return `${API_BASE_URL}${relativePath}`;
};

export default API_BASE_URL;
