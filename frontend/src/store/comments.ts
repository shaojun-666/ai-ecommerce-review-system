import { defineStore } from "pinia"
import { commentsApi } from "@/api"

export const useCommentsStore = defineStore("comments", {
  state: () => ({
    comments: [] as any[],
    total: 0,
    loading: false,
    filters: {} as Record<string, any>,
    currentPage: 1,
    pageSize: 20,
  }),
  actions: {
    async fetchComments(params?: Record<string, any>) {
      this.loading = true
      try {
        const res = await commentsApi.list({ ...this.filters, ...params })
        this.comments = res.data?.items || res.data || []
        this.total = res.data?.total || 0
      } catch {
        this.comments = []
        this.total = 0
      } finally {
        this.loading = false
      }
    },
    async deleteComment(id: number) {
      await commentsApi.delete(id)
      await this.fetchComments()
    },
    setFilters(filters: Record<string, any>) {
      this.filters = filters
    },
  },
})
