import request from "@/utils/request"

export const authApi = {
  login: (data: { username: string; password: string }) =>
    request.post("/auth/login", data),
  refresh: (refresh_token: string) =>
    request.post("/auth/refresh", { refresh_token }),
  me: () => request.get("/auth/me"),
}

export const commentsApi = {
  list: (params?: Record<string, any>) =>
    request.get("/comments", { params }),
  get: (id: number) => request.get(`/comments/${id}`),
  delete: (id: number) => request.delete(`/comments/${id}`),
  batchImport: (file: File, product_id?: number) => {
    const formData = new FormData()
    formData.append("file", file)
    if (product_id) formData.append("product_id", String(product_id))
    return request.post("/comments/batch", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  },
}

export const analysisApi = {
  createTask: (data: { name: string; comment_ids: number[] }) =>
    request.post("/tasks", data),
  listTasks: (params?: Record<string, any>) =>
    request.get("/tasks", { params }),
  getTask: (id: number) => request.get(`/tasks/${id}`),
  getResults: (id: number, params?: Record<string, any>) =>
    request.get(`/tasks/${id}/results`, { params }),
}

export const usersApi = {
  list: () => request.get("/users"),
  create: (data: { username: string; email: string; password: string; role?: string }) =>
    request.post("/users", data),
  update: (id: number, data: Record<string, any>) =>
    request.put(`/users/${id}`, data),
}
