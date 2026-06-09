import { defineStore } from "pinia"
import { analysisApi } from "@/api"
import request from "@/utils/request"

export const useDashboardStore = defineStore("dashboard", {
  state: () => ({
    overview: null as any | null,
    trend: [] as any[],
    keywords: [] as any[],
    loading: false,
  }),
  actions: {
    async fetchOverview() {
      this.loading = true
      try {
        const res = await request.get("/dashboard/overview")
        this.overview = res.data
      } catch {
        this.overview = null
      } finally {
        this.loading = false
      }
    },
    async fetchTrend(days = 30) {
      try {
        const res = await request.get("/dashboard/trend", { params: { days } })
        this.trend = res.data || []
      } catch {
        this.trend = []
      }
    },
    async fetchKeywords(limit = 30) {
      try {
        const res = await request.get("/dashboard/keywords", { params: { limit } })
        this.keywords = res.data || []
      } catch {
        this.keywords = []
      }
    },
    async fetchAll() {
      await Promise.all([
        this.fetchOverview(),
        this.fetchTrend(),
        this.fetchKeywords(),
      ])
    },
  },
})
