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
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="createTask">创建任务</el-button>
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
import { analysisApi } from "@/api"

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
  creating.value = true
  try {
    await analysisApi.createTask({
      name: taskForm.value.name || `Analysis ${Date.now()}`,
      comment_ids: [],
    })
    ElMessage.success("任务已创建")
    taskForm.value.name = ""
    await fetchTasks()
  } catch {
    // handled by interceptor
  } finally {
    creating.value = false
  }
}

onMounted(fetchTasks)
</script>
