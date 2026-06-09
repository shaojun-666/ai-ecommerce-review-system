import axios from "axios"
import { ElMessage } from "element-plus"

const request = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    if (status === 401) {
      // Try refresh
      const refreshToken = localStorage.getItem("refresh_token")
      if (refreshToken) {
        try {
          const res = await axios.post("/api/v1/auth/refresh", { refresh_token: refreshToken })
          localStorage.setItem("access_token", res.data.access_token)
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return request(error.config)
        } catch {
          localStorage.removeItem("access_token")
          localStorage.removeItem("refresh_token")
          window.location.href = "/login"
        }
      } else {
        window.location.href = "/login"
      }
    }
    ElMessage.error(error.response?.data?.error || "Request failed")
    return Promise.reject(error)
  },
)

export default request
