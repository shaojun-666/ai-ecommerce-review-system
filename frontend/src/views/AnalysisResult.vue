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
    </el-card>

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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { analysisApi } from "@/api"

const route = useRoute()
const loading = ref(false)
const task = ref<any>(null)
const results = ref([])

const statusMap: Record<string, string> = {
  pending: "info",
  processing: "warning",
  completed: "success",
  failed: "danger",
  completed_with_errors: "warning",
}

onMounted(async () => {
  const taskId = Number(route.params.taskId)
  loading.value = true
  try {
    const [taskRes, resultsRes] = await Promise.all([
      analysisApi.getTask(taskId),
      analysisApi.getResults(taskId),
    ])
    task.value = taskRes.data.task
    results.value = resultsRes.data.items
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
})
</script>
