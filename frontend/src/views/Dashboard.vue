<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
      <h2 style="margin: 0">数据看板</h2>
      <div style="display: flex; align-items: center; gap: 12px">
        <span v-if="lastUpdated" style="font-size: 12px; color: #999">
          最后更新: {{ lastUpdated }}
        </span>
        <el-button size="small" :loading="refreshing" @click="manualRefresh">
          刷新
        </el-button>
      </div>
    </div>

    <Loading :loading="loading">
      <el-row :gutter="20" style="margin-top: 8px">
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

      <el-row :gutter="20" style="margin-top: 20px">
        <el-col :span="12">
          <el-card>
            <template #header>关键词词云</template>
            <div ref="wordCloudRef" style="height: 350px">无关键词</div>
            <EmptyState :loading="false" :data="keywordData" description="暂无关键词数据" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>最新评论</template>
            <LatestComments :comments="latestComments" :loading="latestLoading" />
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
import EmptyState from "@/components/common/EmptyState.vue"
import LatestComments from "@/components/dashboard/LatestComments.vue"
import * as echarts from "echarts"
import "echarts-wordcloud"
import { connectSocket, disconnectSocket } from "@/utils/socket"

const loading = ref(true)
const refreshing = ref(false)
const taskLoading = ref(false)
const lastUpdated = ref("")
const recentTasks = ref<any[]>([])
const keywordData = ref<any[] | null>(null)
const latestComments = ref<any[]>([])
const latestLoading = ref(false)

const pieRef = ref<HTMLElement>()
const trendRef = ref<HTMLElement>()
const wordCloudRef = ref<HTMLElement>()
let pieChart: any = null
let trendChart: any = null
let wordCloudChart: any = null
let refreshTimer: number | null = null

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

function updateTimestamp() {
  const now = new Date()
  lastUpdated.value = now.toLocaleTimeString("zh-CN", { hour12: false })
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

const renderWordCloud = (data: any[]) => {
  if (!wordCloudRef.value) return
  if (!wordCloudChart) wordCloudChart = echarts.init(wordCloudRef.value)
  if (!data?.length) {
    wordCloudChart.clear()
    return
  }
  wordCloudChart.setOption({
    tooltip: { show: true },
    series: [{
      type: "wordCloud",
      shape: "circle",
      left: "center",
      top: "center",
      width: "90%",
      height: "90%",
      sizeRange: [12, 48],
      rotationRange: [0, 0],
      gridSize: 8,
      drawOutOfBound: false,
      layoutAnimation: true,
      textStyle: {
        fontFamily: "Arial, sans-serif",
        fontWeight: "bold",
        color: () => {
          const colors = ["#409EFF", "#67C23A", "#E6A23C", "#F56C6C", "#909399", "#B37FEB", "#79BBFF"]
          return colors[Math.floor(Math.random() * colors.length)]
        },
      },
      data: data.map((d: any) => ({
        name: d.word,
        value: d.count,
      })),
    }],
  })
}

const resizeCharts = () => {
  pieChart?.resize()
  trendChart?.resize()
  wordCloudChart?.resize()
}

const fetchData = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    const [overviewRes, trendRes, taskRes, keywordRes, latestRes] = await Promise.all([
      request.get("/dashboard/overview").catch(() => ({ data: null })),
      request.get("/dashboard/trend", { params: { days: 30 } }).catch(() => ({ data: [] })),
      analysisApi.listTasks({ per_page: 10 }).catch(() => ({ data: { items: [] } })),
      request.get("/dashboard/keywords", { params: { limit: 50 } }).catch(() => ({ data: [] })),
      request.get("/dashboard/latest-comments", { params: { limit: 10 } }).catch(() => ({ data: [] })),
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

    // Word cloud
    const wcData = keywordRes?.data || []
    keywordData.value = wcData
    await nextTick()
    renderWordCloud(wcData)

    // Latest comments
    latestComments.value = latestRes?.data || []

    updateTimestamp()
  } catch {
    // handled
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const manualRefresh = () => {
  refreshing.value = true
  fetchData(true)
}

onMounted(async () => {
  await fetchData()
  // WebSocket live updates (fallback to 30s polling)
  try {
    const ws = connectSocket()
    ws.on("dashboard_update", () => { fetchData(true) })
    refreshTimer = window.setInterval(() => fetchData(true), 60000)
  } catch {
    refreshTimer = window.setInterval(() => fetchData(true), 30000)
  }
})

onUnmounted(() => {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  try { disconnectSocket() } catch { /* ignore */ }
  window.removeEventListener("resize", resizeCharts)
  pieChart?.dispose()
  trendChart?.dispose()
  wordCloudChart?.dispose()
})

window.addEventListener("resize", resizeCharts)
</script>
