import axios from 'axios'
import { ElMessage } from 'element-plus'
import { clearSession, session } from '../stores/session'

function defaultApiBaseUrl() {
  if (typeof window === 'undefined') return 'http://localhost:8000/api/v1'
  return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl(),
  timeout: 15000
})

apiClient.interceptors.request.use((config) => {
  if (session.token) {
    config.headers.Authorization = `Bearer ${session.token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const requestUrl = error.config?.url || ''
    if (status === 401 && !requestUrl.includes('/auth/login')) {
      clearSession()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    } else if (status === 403) {
      ElMessage.warning('当前账号没有权限执行该操作')
    }
    return Promise.reject(error)
  }
)
