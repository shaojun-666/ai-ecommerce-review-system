import { defineStore } from "pinia"
import { analysisApi } from "@/api"

export const useAnalysisStore = defineStore("analysis", {
  state: () => ({
    tasks: [] as any[],
    currentTask: null as any | null,
    results: [] as any[],
    resultsTotal: 0,
    loading: false,
    pollTimer: null as any,
  }),
  actions: {
    async fetchTasks(params?: Record<string, any>) {
      this.loading = true
      try {
        const res = await analysisApi.listTasks(params)
        this.tasks = res.data?.items || res.data || []
      } finally {
        this.loading = false
      }
    },
    async getTask(id: number) {
      try {
        const res = await analysisApi.getTask(id)
        this.currentTask = res.data
        return res.data
      } catch {
        return null
      }
    },
    async fetchResults(id: number, params?: Record<string, any>) {
      try {
        const res = await analysisApi.getResults(id, params)
        this.results = res.data?.items || res.data || []
        this.resultsTotal = res.data?.total || 0
        return res
      } catch {
        this.results = []
        return null
      }
    },
    async createTask(data: { name: string; comment_ids: number[] }) {
      const res = await analysisApi.createTask(data)
      return res.data
    },
    startPolling(taskId: number, callback: (task: any) => void) {
      this.stopPolling()
      this.pollTimer = setInterval(async () => {
        const task = await this.getTask(taskId)
        if (task) callback(task)
        if (task?.status === "completed" || task?.status === "failed" || task?.status === "completed_with_errors") {
          this.stopPolling()
        }
      }, 3000)
    },
    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
  },
})
