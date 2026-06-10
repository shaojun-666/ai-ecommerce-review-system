<template>
  <div>
    <h2>分析结果</h2>
    <el-card v-if="task" style="margin-top: 16px">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="任务名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusMap[task.status] || 'info'">{{ task.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ task.processed_count }}/{{ task.total_count }}</el-descriptions-item>
      </el-descriptions>

      <!-- Progress bar for in-progress tasks -->
      <div v-if="task.status === 'processing'" style="margin-top: 16px">
        <el-progress
          :percentage="progressPercent"
          :stroke-width="20"
          :text-inside="true"
          status="warning"
        />
        <div v-if="pollTimeout" style="margin-top: 8px; color: #E6A23C; font-size: 13px">
          ⚠ 轮询超时，任务仍在处理中，请手动刷新
        </div>
      </div>

      <div v-if="task.status === 'completed' || task.status === 'completed_with_errors'" style="margin-top: 16px">
        <el-progress
          :percentage="100"
          :stroke-width="20"
          :text-inside="true"
          status="success"
        />
      </div>
    </el-card>

    <ErrorState :error="fetchError" @retry="fetchData">
      <el-card style="margin-top: 16px">
        <el-table :data="results" v-loading="loading" stripe style="width: 100%">
          <el-table-column prop="comment_id" label="评论 ID" width="80" />
          <el-table-column prop="sentiment" label="情感" width="80">
            <template #default="{ row }">
              <el-tag :type="row.sentiment === 'positive' ? 'success' : row.sentiment === 'negative' ? 'danger' : 'info'" size="small">
                {{ row.sentiment }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sentiment_score" label="置信度" width="80" />
          <el-table-column prop="fake_score" label="虚假评分" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.fake_score && row.fake_score > 0.7" type="danger" size="small">
                {{ (row.fake_score * 100).toFixed(0) }}%
              </el-tag>
              <span v-else>{{ row.fake_score ? (row.fake_score * 100).toFixed(0) + '%' : '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="aspects" label="细粒度维度" width="200">
            <template #default="{ row }">
              <span v-if="row.aspects">{{ JSON.stringify(row.aspects) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="keywords" label="关键词" width="200">
            <template #default="{ row }">
              <el-tag v-for="kw in (row.keywords || [])" :key="kw" size="small" style="margin: 2px">
                {{ kw }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="analyzed_at" label="分析时间" width="160" />
        </el-table>
      </el-card>
    </ErrorState>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue"
import { useRoute } from "vue-router"
import { analysisApi } from "@/api"
import ErrorState from "@/components/common/ErrorState.vue"

const route = useRoute()
const loading = ref(false)
const fetchError = ref(false)
const task = ref<any>(null)
const results = ref([])
const pollTimeout = ref(false)

let pollTimer: number | null = null
let pollCount = 0
const MAX_POLLS = 60 // 5 minutes at 5s interval

const progressPercent = computed(() => {
  if (!task.value?.total_count) return 0
  return Math.round((task.value.processed_count / task.value.total_count) * 100)
})

const statusMap: Record<string, string> = {
  pending: "info",
  processing: "warning",
  completed: "success",
  failed: "danger",
  completed_with_errors: "warning",
}

const isTerminal = (status: string) =>
  ["completed", "failed", "completed_with_errors"].includes(status)

const fetchData = async () => {
  const taskId = Number(route.params.taskId)
  loading.value = true
  fetchError.value = false
  try {
    const [taskRes, resultsRes] = await Promise.all([
      analysisApi.getTask(taskId),
      analysisApi.getResults(taskId),
    ])
    task.value = taskRes.data.task
    results.value = resultsRes.data.items

    // Start polling if still processing
    if (task.value?.status === "processing" && pollTimer === null) {
      startPolling()
    }
  } catch {
    fetchError.value = true
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  pollCount = 0
  pollTimeout.value = false
  pollTimer = window.setInterval(async () => {
    pollCount++
    if (pollCount > MAX_POLLS) {
      stopPolling()
      pollTimeout.value = true
      return
    }

    try {
      const taskId = Number(route.params.taskId)
      const taskRes = await analysisApi.getTask(taskId)
      task.value = taskRes.data.task

      if (isTerminal(task.value.status)) {
        stopPolling()
        // Refresh results
        const resultsRes = await analysisApi.getResults(taskId)
        results.value = resultsRes.data.items
      }
    } catch {
      // keep polling
    }
  }, 5000)
}

const stopPolling = () => {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(fetchData)

onUnmounted(stopPolling)
</script>
