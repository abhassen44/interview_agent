import axios from 'axios';

// Create axios instance with base URL
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '',
});

// Resume upload
export const uploadResume = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload-resume/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  
  return response.data;
};

// Start interview
export const startInterview = async (sessionId) => {
  const response = await api.get(`/start-interview/${sessionId}`);
  return response.data;
};

// Submit answer
export const submitAnswer = async (sessionId, answer) => {
  const response = await api.post('/submit-answer/', {
    session_id: sessionId,
    answer: answer
  });
  
  return response.data;
};

// Get scorecard
export const getScorecard = async (sessionId) => {
  const response = await api.get(`/scorecard/${sessionId}`);
  return response.data;
};

// End interview
export const endInterview = async (sessionId) => {
  const response = await api.post(`/end-interview/${sessionId}`);
  return response.data;
};

// Delete session
export const deleteSession = async (sessionId) => {
  const response = await api.delete(`/session/${sessionId}`);
  return response.data;
};

export default api;