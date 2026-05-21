import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

// Dołącza token JWT do każdego żądania
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
