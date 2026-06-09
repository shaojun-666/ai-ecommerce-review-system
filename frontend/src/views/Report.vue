<template>
  <div>
    <h2>报告管理</h2>
    <el-card style="margin-top: 20px">
      <template #header>导出分析报告</template>
      <el-form label-width="120px">
        <el-form-item label="分析任务">
          <el-select v-model="selectedTask" filterable placeholder="请选择分析任务" style="width: 100%">
            <el-option
              v-for="t in tasks"
              :key="t.id"
              :label="t.name"
              :value="t.id"
              :disabled="t.status !== 'completed'"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="format">
            <el-radio value="csv">CSV</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!selectedTask" @click="exportReport">
            导出报告
          </el-button>
          <el-button @click="exportSummary">
            导出总览摘要
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>最近报告</template>
      <el-empty v-if="tasks.length === 0" description="暂无已完成的分析任务" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { analysisApi } from "@/api"
import { ElMessage } from "element-plus"

const tasks = ref<any[]>([])
const selectedTask = ref<number | null>(null)
const format = ref("csv")

onMounted(async () => {
  try {
    const res = await analysisApi.listTasks({ per_page: 50 })
    tasks.value = res.data?.items || res.data || []
  } catch {
    tasks.value = []
  }
})

const exportReport = () => {
  if (!selectedTask.value) return
  window.open(`/api/v1/reports/export/${selectedTask.value}?format=${format.value}`, "_blank")
  ElMessage.success("报告下载中")
}

const exportSummary = () => {
  window.open("/api/v1/reports/summary", "_blank")
  ElMessage.success("摘要下载中")
}
</script>
