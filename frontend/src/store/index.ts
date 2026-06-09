import { defineStore } from "pinia"
import { authApi } from "@/api"

export const useUserStore = defineStore("user", {
  state: () => ({
    user: null as Record<string, any> | null,
    accessToken: localStorage.getItem("access_token") || "",
    refreshToken: localStorage.getItem("refresh_token") || "",
  }),
  getters: {
    isLoggedIn: (state) => !!state.accessToken,
    isAdmin: (state) => state.user?.role === "admin",
  },
  actions: {
    setUser(user: Record<string, any>) {
      this.user = user
    },
    setTokens(access: string, refresh: string) {
      this.accessToken = access
      this.refreshToken = refresh
      localStorage.setItem("access_token", access)
      localStorage.setItem("refresh_token", refresh)
    },
    async fetchUser() {
      try {
        const res = await authApi.me()
        this.user = res.data
      } catch {
        this.logout()
      }
    },
    async login(username: string, password: string) {
      const res = await authApi.login({ username, password })
      this.setTokens(res.data.access_token, res.data.refresh_token)
      await this.fetchUser()
      return res
    },
    logout() {
      this.user = null
      this.accessToken = ""
      this.refreshToken = ""
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
    },
  },
})

export { useCommentsStore } from "./comments"
export { useAnalysisStore } from "./analysis"
export { useDashboardStore } from "./dashboard"
