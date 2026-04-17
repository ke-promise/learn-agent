import axios from 'axios'

// 所有前端请求都通过这一个 axios 实例发出，方便统一配置基地址和超时。
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
})

export default api