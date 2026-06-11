<template>
  <div>
    <h2>商品对比</h2>

    <el-card style="margin-top: 16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="12">
          <span style="margin-right: 8px">选择要对比的商品:</span>
          <el-select
            v-model="selectedProductIds"
            multiple
            placeholder="选择 2-4 个商品"
            style="width: 400px"
            @change="loadComparison"
          >
            <el-option v-for="p in allProducts" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="12" style="text-align: right">
          <el-button :disabled="selectedProductIds.length < 2" type="primary" @click="loadComparison">刷新对比</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Comparison cards -->
    <div v-if="comparisonData.length" style="display: flex; gap: 16px; margin-top: 16px; overflow-x: auto; padding-bottom: 8px">
      <el-card v-for="p in comparisonData" :key="p.id" style="min-width: 300px; flex: 1">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <strong>{{ p.name }}</strong>
            <el-tag size="small">{{ p.platform || '-' }}</el-tag>
          </div>
        </template>

        <!-- Basic info -->
        <div style="margin-bottom: 16px">
          <div v-for="t in (p.tags || [])" :key="t.id" style="display: inline-block; margin-right: 4px; margin-bottom: 4px">
            <el-tag :color="t.color" size="small" style="color: #fff">{{ t.name }}</el-tag>
          </div>
        </div>

        <!-- Metrics grid -->
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="当前价格">
            <span v-if="p.monitoring?.latest_price" style="font-size: 18px; font-weight: bold; color: #f56c6c">
              ¥{{ p.monitoring.latest_price }}
            </span>
            <span v-else style="color: #999">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="评论增长(14d)">
            <span v-if="p.monitoring?.comment_growth_14d != null" :style="growthStyle(p.monitoring.comment_growth_14d)">
              {{ p.monitoring.comment_growth_14d > 0 ? '+' : '' }}{{ p.monitoring.comment_growth_14d }}%
            </span>
            <span v-else style="color: #999">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="评论总数">
            <span style="font-size: 18px; font-weight: bold; color: #409eff">
              {{ p.monitoring?.comment_count || 0 }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="正面评论">
            <span v-if="p.sentimentStats" style="color: #67c23a">{{ p.sentimentStats.positive }}</span>
            <span v-else style="color: #999">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="负面评论">
            <span v-if="p.sentimentStats" style="color: #f56c6c">{{ p.sentimentStats.negative }}</span>
            <span v-else style="color: #999">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="好评率">
            <span v-if="p.sentimentStats" style="font-weight: bold">
              {{ p.sentimentStats.rate }}%
            </span>
            <span v-else style="color: #999">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="监控状态">
            <el-tag v-if="p.monitoring?.crawl_task" :type="taskStatusType(p.monitoring.crawl_task.status)" size="small">
              {{ taskStatusLabel(p.monitoring.crawl_task.status) }}
            </el-tag>
            <span v-else style="color: #999">未配置</span>
          </el-descriptions-item>
          <el-descriptions-item label="最近采集">
            {{ formatTime(p.monitoring?.crawl_task?.completed_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="数据新鲜度">
            <el-tag v-if="p.monitoring?.last_comment_date" :type="freshnessType(p.monitoring.last_comment_date)" size="small">
              {{ freshnessLabel(p.monitoring.last_comment_date) }}
            </el-tag>
            <span v-else style="color: #999">无数据</span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- Sentiment bar -->
        <div v-if="p.sentimentStats" style="margin-top: 16px">
          <div style="font-size: 13px; margin-bottom: 4px">情感分布</div>
          <el-progress
            :percentage="p.sentimentStats.positiveRate"
            :color="'#67c23a'"
            :format="() => `正面 ${p.sentimentStats.positiveRate}%`"
          />
          <el-progress
            :percentage="p.sentimentStats.neutralRate"
            :color="'#e6a23c'"
            :format="() => `中性 ${p.sentimentStats.neutralRate}%`"
            style="margin-top: 4px"
          />
          <el-progress
            :percentage="p.sentimentStats.negativeRate"
            :color="'#f56c6c'"
            :format="() => `负面 ${p.sentimentStats.negativeRate}%`"
            style="margin-top: 4px"
          />
        </div>
        <div v-else style="margin-top: 16px; color: #999; font-size: 13px">
          暂无情感分析数据，请先运行分析任务
        </div>
      </el-card>
    </div>

    <!-- Empty state -->
    <el-card v-else style="margin-top: 16px">
      <div style="text-align: center; padding: 40px; color: #999">
        请选择 2-4 个商品进行对比
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { productsApi } from "@/api"
import request from "@/utils/request"

const allProducts = ref<any[]>([])
const selectedProductIds = ref<number[]>([])
const comparisonData = ref<any[]>([])

onMounted(async () => {
  try {
    const res = await productsApi.list({ per_page: 200 })
    const d = res.data
    allProducts.value = d?.data?.items || d?.data?.data || d?.data || []
  } catch {
    allProducts.value = []
  }
})

const loadComparison = async () => {
  if (selectedProductIds.value.length < 2) return
  const results: any[] = []
  for (const id of selectedProductIds.value) {
    try {
      const res = await request.get(`/products/${id}`)
      const product = res.data?.data
      if (product) {
        product.sentimentStats = await loadSentimentStats(id)
        results.push(product)
      }
    } catch {
      // skip failed
    }
  }
  comparisonData.value = results
}

const loadSentimentStats = async (productId: number) => {
  try {
    const res = await request.get("/dashboard/summary", { params: { product_id: productId } })
    const data = res.data?.data
    if (!data) return null
    const positive = data.positive_comments || 0
    const negative = data.negative_comments || 0
    const neutral = data.neutral_comments || 0
    const total = positive + negative + neutral
    if (!total) return null
    return {
      positive,
      negative,
      neutral,
      total,
      rate: total ? Math.round((positive / total) * 100) : 0,
      positiveRate: Math.round((positive / total) * 100),
      negativeRate: Math.round((negative / total) * 100),
      neutralRate: Math.round((neutral / total) * 100),
    }
  } catch {
    return null
  }
}

const growthStyle = (rate: number) => {
  if (rate > 10) return { color: '#f56c6c', fontWeight: 'bold' as const }
  if (rate > 0) return { color: '#e6a23c', fontWeight: 'bold' as const }
  if (rate < -10) return { color: '#67c23a', fontWeight: 'bold' as const }
  return { color: '#909399' }
}

const taskStatusMap: Record<string, string> = {
  pending: "info", processing: "warning", crawling: "warning",
  filtering: "warning", completed: "success", failed: "danger",
}
const taskStatusType = (s: string) => taskStatusMap[s] || "info"
const taskStatusLabel = (s: string) => {
  const m: Record<string, string> = { pending: "待处理", crawling: "采集中", filtering: "过滤中", completed: "已完成", failed: "失败" }
  return m[s] || s
}
const freshnessType = (dateStr: string) => {
  if (!dateStr) return "info"
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = diff / 3600000
  if (hours < 24) return "success"
  if (hours < 72) return "warning"
  return "danger"
}
const freshnessLabel = (dateStr: string) => {
  if (!dateStr) return "未知"
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.round(diff / 3600000)
  if (hours < 1) return "刚刚"
  if (hours < 24) return `${hours}小时前`
  const days = Math.round(hours / 24)
  return `${days}天前`
}
const formatTime = (s: string) => {
  if (!s) return "-"
  return new Date(s).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
}
</script>
