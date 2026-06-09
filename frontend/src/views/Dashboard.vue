<template>
  <div>
    <h2>数据看板</h2>

    <Loading :loading="loading">
      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="6" v-for="stat in stats" :key="stat.label">
          <el-card shadow="hover">
            <div style="text-align: center">
              <div style="font-size: 32px; font-weight: bold" :style="{ color: stat.color }">{{ stat.value }}</div>
              <div style="color: #999; margin-top: 8px">{{ stat.label }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <el-card>
            <template #header>情感分布</template>
            <div ref="pieRef" style="height: 350px"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>情感趋势 (近30天)</template>
            <div ref="trendRef" style="height: 350px"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card style="margin-top: 20px">
        <template #header>
          <span>最近分析任务</span>
          <router-link to="/analysis" style="float: right; font-size: 14px">查看全部</router-link>
        </template>
        <el-table :data="recentTasks" v-loading="taskLoading" stripe style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="任务名称" />
          <el-table-column prop="status" label="状态" width="140">
            <template #default="{ row }">
              <el-tag :type="statusMap[row.status] || 'info'">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="total_count" label="总数" width="80" />
          <el-table-column prop="processed_count" label="已处理" width="80" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="$router.push(`/analysis/${row.id}`)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </Loading>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from "vue"
import { analysisApi } from "@/api"
import request from "@/utils/request"
import Loading from "@/components/common/Loading.vue"
import * as echarts from "echarts"

const loading = ref(true)
const taskLoading = ref(false)
const recentTasks = ref<any[]>([])
const pieRef = ref<HTMLElement>()
const trendRef = ref<HTMLElement>()
let pieChart: any = null
let trendChart: any = null

const stats = ref([
  { label: "评论总数", value: 0, color: "#409EFF" },
  { label: "已分析", value: 0, color: "#67C23A" },
  { label: "虚假评论", value: 0, color: "#E6A23C" },
  { label: "平均评分", value: 0, color: "#F56C6C" },
])

const statusMap: Record<string, string> = {
  pending: "info",
  processing: "warning",
  completed: "success",
  failed: "danger",
  completed_with_errors: "warning",
}

const renderPie = (sentiment: any) => {
  if (!pieRef.value) return
  if (!pieChart) pieChart = echarts.init(pieRef.value)
  pieChart.setOption({
    tooltip: { trigger: "item" },
    series: [{
      type: "pie",
      radius: ["40%", "70%"],
      data: [
        { value: sentiment?.positive?.count || 0, name: "正面", itemStyle: { color: "#67C23A" } },
        { value: sentiment?.negative?.count || 0, name: "负面", itemStyle: { color: "#F56C6C" } },
        { value: sentiment?.neutral?.count || 0, name: "中性", itemStyle: { color: "#909399" } },
      ],
      label: { show: true, formatter: "{b}: {c} ({d}%)" },
    }],
  })
}

const renderTrend = (data: any[]) => {
  if (!trendRef.value || !data?.length) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["正面", "负面", "中性"] },
    xAxis: { type: "category", data: data.map((d: any) => d.date?.slice(5) || "") },
    yAxis: { type: "value" },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    series: [
      { name: "正面", type: "line", data: data.map((d: any) => d.positive || 0), itemStyle: { color: "#67C23A" }, smooth: true },
      { name: "负面", type: "line", data: data.map((d: any) => d.negative || 0), itemStyle: { color: "#F56C6C" }, smooth: true },
      { name: "中性", type: "line", data: data.map((d: any) => d.neutral || 0), itemStyle: { color: "#909399" }, smooth: true },
    ],
  })
}

const resizeCharts = () => {
  pieChart?.resize()
  trendChart?.resize()
}

onMounted(async () => {
  loading.value = true
  try {
    const [overviewRes, trendRes, taskRes] = await Promise.all([
      request.get("/dashboard/overview").catch(() => ({ data: null })),
      request.get("/dashboard/trend", { params: { days: 30 } }).catch(() => ({ data: [] })),
      analysisApi.listTasks({ per_page: 10 }).catch(() => ({ data: { items: [] } })),
    ])

    const overview = overviewRes?.data
    if (overview) {
      stats.value[0].value = overview.total_comments || 0
      stats.value[1].value = overview.analyzed_count || 0
      stats.value[2].value = overview.fake_review_count || 0
      stats.value[3].value = overview.avg_rating || 0

      await nextTick()
      renderPie(overview.sentiment_distribution)
    }

    if (trendRes?.data) renderTrend(trendRes.data)
    recentTasks.value = taskRes?.data?.items || []
  } catch {
    // handled
  } finally {
    loading.value = false
  }
})

window.addEventListener("resize", resizeCharts)

onUnmounted(() => {
  window.removeEventListener("resize", resizeCharts)
  pieChart?.dispose()
  trendChart?.dispose()
})
</script>
