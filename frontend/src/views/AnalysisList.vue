<template>
  <div>
    <h2>分析中心</h2>
    <el-card style="margin-top: 16px">
      <template #header>新建分析任务</template>
      <el-form :model="taskForm" label-width="120px">
        <el-form-item label="任务名称">
          <el-input v-model="taskForm.name" placeholder="例如: 6月评论分析" style="max-width: 400px" />
        </el-form-item>
        <el-form-item label="分析类型">
          <el-select v-model="taskForm.type" style="width: 200px">
            <el-option label="完整分析" value="full" />
            <el-option label="仅情感" value="sentiment" />
            <el-option label="关键词提取" value="keyword" />
            <el-option label="评论摘要" value="summary" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择商品">
          <el-select
            v-model="selectedProductId"
            placeholder="选择商品"
            style="width: 300px"
            clearable
            filterable
            @change="onProductChange"
          >
            <el-option
              v-for="p in products"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="选择评论">
          <div style="width: 100%">
            <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 12px">
              <span>已选 {{ selectedCommentIds.length }} 条</span>
              <el-button size="small" @click="selectAllComments">全选</el-button>
              <el-button size="small" @click="selectedCommentIds = []">清空</el-button>
              <el-button size="small" @click="selectAllUnanalyzed">仅未分析</el-button>
            </div>
            <el-table
              ref="commentTableRef"
              :data="comments"
              v-loading="commentsLoading"
              stripe
              style="width: 100%"
              max-height="360"
              @selection-change="onSelectionChange"
            >
              <el-table-column type="selection" width="40" />
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="content" label="评论内容" min-width="300" show-overflow-tooltip />
              <el-table-column prop="rating" label="评分" width="60" />
              <el-table-column label="已分析" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.analysis" type="success" size="small">是</el-tag>
                  <el-tag v-else type="info" size="small">否</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              v-if="commentTotal > commentPerPage"
              v-model:current-page="commentPage"
              :page-size="commentPerPage"
              :total="commentTotal"
              layout="prev, pager, next"
              small
              style="margin-top: 8px; justify-content: center"
              @current-change="loadComments"
            />
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" :disabled="selectedCommentIds.length === 0" @click="createTask">
            创建任务 (分析 {{ selectedCommentIds.length }} 条评论)
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>分析任务列表</template>
      <el-table :data="tasks" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="任务名称" min-width="200" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status] || 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="总数" width="70" />
        <el-table-column prop="processed_count" label="已处理" width="70" />
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.total_count ? Math.round(row.processed_count / row.total_count * 100) : 0"
              :status="row.status === 'failed' ? 'exception' : row.status === 'completed' ? 'success' : undefined"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/analysis/${row.id}`)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import { analysisApi, commentsApi, productsApi } from "@/api"

const loading = ref(false)
const creating = ref(false)
const tasks = ref<any[]>([])

const taskForm = ref({ name: "", type: "full" })

const statusMap: Record<string, string> = {
  pending: "info",
  processing: "warning",
  completed: "success",
  failed: "danger",
  completed_with_errors: "warning",
}

// Product & comment selection
const products = ref<any[]>([])
const selectedProductId = ref<number | undefined>()
const comments = ref<any[]>([])
const commentsLoading = ref(false)
const commentTotal = ref(0)
const commentPage = ref(1)
const commentPerPage = 50
const selectedCommentIds = ref<number[]>([])
const commentTableRef = ref()

const fetchProducts = async () => {
  try {
    const res = await productsApi.list()
    products.value = res.data?.data?.items || res.data?.data || []
  } catch {
    products.value = []
  }
}

const onProductChange = () => {
  commentPage.value = 1
  selectedCommentIds.value = []
  loadComments()
}

const loadComments = async () => {
  if (!selectedProductId.value) {
    comments.value = []
    return
  }
  commentsLoading.value = true
  try {
    const res = await commentsApi.list({
      product_id: selectedProductId.value,
      page: commentPage.value,
      per_page: commentPerPage,
    })
    comments.value = res.data.items || []
    commentTotal.value = res.data.total || 0
  } catch {
    comments.value = []
  } finally {
    commentsLoading.value = false
  }
}

const onSelectionChange = (selection: any[]) => {
  selectedCommentIds.value = selection.map((c: any) => c.id)
}

const selectAllComments = () => {
  if (!commentTableRef.value) return
  commentTableRef.value.clearSelection()
  commentTableRef.value.toggleAllSelection()
}

const selectAllUnanalyzed = () => {
  if (!commentTableRef.value) return
  commentTableRef.value.clearSelection()
  const unanalyzed = comments.value.filter((c: any) => !c.analysis)
  unanalyzed.forEach((c: any) => {
    commentTableRef.value.toggleRowSelection(c, true)
  })
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const res = await analysisApi.listTasks({ per_page: 50 })
    tasks.value = res.data?.items || res.data || []
  } catch {
    tasks.value = []
  } finally {
    loading.value = false
  }
}

const createTask = async () => {
  if (selectedCommentIds.value.length === 0) {
    ElMessage.warning("请至少选择一条评论")
    return
  }
  creating.value = true
  try {
    await analysisApi.createTask({
      name: taskForm.value.name || `Analysis ${Date.now()}`,
      comment_ids: selectedCommentIds.value,
    })
    ElMessage.success(`任务已创建，分析 ${selectedCommentIds.value.length} 条评论`)
    taskForm.value.name = ""
    selectedCommentIds.value = []
    if (commentTableRef.value) {
      commentTableRef.value.clearSelection()
    }
    await fetchTasks()
  } catch {
    // handled by interceptor
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  fetchTasks()
  fetchProducts()
})
</script>
