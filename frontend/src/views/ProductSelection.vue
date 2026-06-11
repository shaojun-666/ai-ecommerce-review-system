<template>
  <div>
    <h2>选品中心</h2>

    <!-- Category heat (P10-4) -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <strong>品类热度</strong>
          <el-radio-group v-model="heatDays" size="small" @change="loadCategoryHeat">
            <el-radio-button :value="7">7天</el-radio-button>
            <el-radio-button :value="30">30天</el-radio-button>
            <el-radio-button :value="90">90天</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <div v-if="categoryHeat.length" style="display: flex; gap: 16px; overflow-x: auto; padding-bottom: 8px">
        <div
          v-for="cat in categoryHeat"
          :key="cat.tag_id"
          :style="heatCardStyle(cat.tag_id)"
          @click="onHeatCardClick(cat.tag_id)"
        >
          <div style="text-align: center">
            <h3 style="margin: 0 0 8px">{{ cat.tag_name }}</h3>
            <div style="font-size: 28px; font-weight: bold; color: #409eff">{{ cat.heat_score }}</div>
            <div style="font-size: 12px; color: #999; margin-bottom: 12px">热度分</div>
            <el-row :gutter="8" style="font-size: 12px">
              <el-col :span="12">商品: {{ cat.product_count }}</el-col>
              <el-col :span="12">评论: {{ cat.comment_count }}</el-col>
            </el-row>
            <el-row :gutter="8" style="font-size: 12px; margin-top: 4px">
              <el-col :span="12">
                增长:
                <span :style="cat.comment_growth_rate > 0 ? 'color: #f56c6c;' : 'color: #67c23a;'">
                  {{ cat.comment_growth_rate > 0 ? '+' : '' }}{{ cat.comment_growth_rate }}%
                </span>
              </el-col>
              <el-col :span="12">
                好评: <span style="color: #67c23a">{{ cat.positive_rate }}%</span>
              </el-col>
            </el-row>
          </div>
        </div>
      </div>
      <div v-else style="text-align: center; padding: 20px; color: #999">
        {{ heatLoading ? '加载中...' : '暂无品类数据，请先创建商品标签' }}
      </div>
    </el-card>

    <!-- AI Recommendations (P10-5) -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <strong>
            AI 选品建议
            <el-tag v-if="recommendations?.summary" type="warning" size="small" style="margin-left: 8px">
              {{ recommendations.recommendations?.length || 0 }} 条推荐
            </el-tag>
          </strong>
          <el-button size="small" :loading="recLoading" @click="loadRecommendations">刷新</el-button>
        </div>
      </template>

      <!-- Summary -->
      <div v-if="recommendations?.summary" style="background: #f0f9eb; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px; font-size: 14px; color: #67c23a">
        {{ recommendations.summary }}
      </div>

      <!-- Alerts -->
      <div v-if="recommendations?.alerts?.length">
        <div v-for="alert in recommendations.alerts" :key="alert" style="background: #fef0f0; padding: 8px 12px; border-radius: 4px; margin-bottom: 8px; font-size: 13px; color: #f56c6c">
          ⚠ {{ alert }}
        </div>
      </div>

      <!-- Recommendations table -->
      <el-table v-if="recommendations?.recommendations?.length" :data="recommendations.recommendations" size="small" stripe>
        <el-table-column label="商品" min-width="160">
          <template #default="{ row }">
            <div style="font-weight: bold">{{ row.product_name }}</div>
            <div v-if="row.tags?.length" style="margin-top: 2px">
              <el-tag v-for="t in row.tags" :key="t" size="small" style="margin-right: 2px">{{ t }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="综合评分" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.composite_score >= 70 ? 'success' : row.composite_score >= 50 ? 'warning' : 'danger'">
              {{ row.composite_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="actionType(row.action?.action)" size="small">
              {{ row.action?.label || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="依据" min-width="240">
          <template #default="{ row }">
            <div v-for="r in row.reasons" :key="r" style="font-size: 12px; color: #666; line-height: 1.6">
              • {{ r }}
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- Insights -->
      <el-collapse v-if="recommendations?.insights?.length" style="margin-top: 12px">
        <el-collapse-item title="品类洞察" name="insights">
          <div v-for="insight in recommendations.insights" :key="insight" style="padding: 4px 0; font-size: 13px; color: #666">
            • {{ insight }}
          </div>
        </el-collapse-item>
      </el-collapse>

      <div v-if="recLoading" style="text-align: center; padding: 20px; color: #999">加载中...</div>
      <div v-else-if="!recommendations" style="text-align: center; padding: 20px; color: #999">
        暂无选品建议，请先确保已有商品和评论数据
      </div>
    </el-card>

    <!-- Uptrend products (P10-3) -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <strong>
            上行期商品
            <el-tag v-if="uptrendProducts.length" type="success" size="small" style="margin-left: 8px">
              发现 {{ uptrendProducts.length }} 个
            </el-tag>
          </strong>
          <el-button size="small" :loading="loading" @click="loadUptrend">刷新</el-button>
        </div>
      </template>

      <!-- Product cards -->
      <div v-if="uptrendProducts.length" style="display: flex; flex-direction: column; gap: 12px">
        <el-card
          v-for="item in uptrendProducts"
          :key="item.product_id"
          shadow="hover"
          :body-style="{ padding: '16px' }"
        >
          <el-row :gutter="16" align="middle">
            <!-- Score section -->
            <el-col :span="3" style="text-align: center">
              <div :style="scoreRingStyle(item.composite_score)" style="width: 64px; height: 64px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold">
                {{ item.composite_score }}
              </div>
              <div style="font-size: 12px; color: #999; margin-top: 4px">综合评分</div>
            </el-col>

            <!-- Product info -->
            <el-col :span="7">
              <div style="font-weight: bold; font-size: 16px">{{ item.product_name }}</div>
              <div style="font-size: 13px; color: #666; margin-top: 4px">
                <el-tag size="small">{{ item.platform || '未知平台' }}</el-tag>
                <span v-if="item.latest_price" style="margin-left: 8px; color: #f56c6c">
                  ¥{{ item.latest_price }}
                </span>
              </div>
              <div v-if="item.uptrend" style="margin-top: 6px">
                <el-progress
                  :percentage="item.uptrend.confidence"
                  :color="confidenceColor(item.uptrend.confidence)"
                  :stroke-width="8"
                  :format="() => `置信度 ${item.uptrend.confidence}%`"
                />
              </div>
            </el-col>

            <!-- Dimension scores -->
            <el-col :span="10">
              <el-row :gutter="8">
                <el-col :span="6" v-for="(val, key) in item.dimensions" :key="key">
                  <div style="text-align: center">
                    <div :style="'font-size: 18px; font-weight: bold; color: ' + dimColor(val.score)">
                      {{ val.score }}
                    </div>
                    <div style="font-size: 11px; color: #999">{{ dimLabel(key) }}</div>
                    <div style="font-size: 11px">
                      <span v-if="val.growth_rate != null" :style="val.growth_rate > 0 ? 'color: #f56c6c' : 'color: #67c23a'">
                        {{ val.growth_rate > 0 ? '+' : '' }}{{ val.growth_rate }}%
                      </span>
                      <span v-else-if="val.trend" :style="trendColor(val.trend)">{{ trendLabel(val.trend) }}</span>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </el-col>

            <!-- Signals -->
            <el-col :span="4" style="text-align: right">
              <div v-if="item.uptrend">
                <el-tag
                  v-for="(active, sig) in item.uptrend.signals"
                  :key="sig"
                  :type="active ? 'success' : 'info'"
                  size="small"
                  style="margin: 2px; display: inline-block"
                >
                  {{ signalLabel(sig) }}
                </el-tag>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </div>

      <!-- Empty state -->
      <div v-else style="text-align: center; padding: 40px; color: #999">
        <div v-if="loading">加载中...</div>
        <div v-else>
          <p>暂未发现处于上行期的商品</p>
          <p style="font-size: 13px">上行期检测需要足够的评论数据(至少28天跨度)和分析结果</p>
        </div>
      </div>

      <!-- Error state -->
      <div v-if="error" style="text-align: center; padding: 20px; color: #f56c6c">
        加载失败: {{ error }}
        <el-button size="small" style="margin-left: 8px" @click="loadUptrend">重试</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import request from "@/utils/request"

const loading = ref(false)
const error = ref("")
const uptrendProducts = ref<any[]>([])

// Category heat
const heatDays = ref(30)
const heatLoading = ref(false)
const categoryHeat = ref<any[]>([])
const selectedTagId = ref<number | null>(null)

// AI Recommendations
const recLoading = ref(false)
const recommendations = ref<any>(null)

const loadUptrend = async () => {
  loading.value = true
  error.value = ""
  try {
    const res = await request.get("/products/uptrend")
    const data = res.data?.data || res.data || []
    // Merge uptrend detection into each item
    uptrendProducts.value = data
  } catch (e: any) {
    error.value = e?.message || "请求失败"
    uptrendProducts.value = []
  } finally {
    loading.value = false
  }
}

const loadCategoryHeat = async () => {
  heatLoading.value = true
  try {
    const res = await request.get("/dashboard/category-heat", { params: { days: heatDays.value } })
    categoryHeat.value = res.data?.data || []
  } catch {
    categoryHeat.value = []
  } finally {
    heatLoading.value = false
  }
}

const onHeatCardClick = (tagId: number) => {
  selectedTagId.value = selectedTagId.value === tagId ? null : tagId
}

const heatCardStyle = (tagId: number) => {
  const base = "min-width: 200px; flex-shrink: 0; cursor: pointer; border-radius: 8px; padding: 16px; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.08);"
  if (tagId === selectedTagId.value) {
    return base + " border: 2px solid #409eff;"
  }
  return base + " border: 1px solid #ebeef5;"
}

const loadRecommendations = async () => {
  recLoading.value = true
  try {
    const res = await request.get("/products/recommendations")
    recommendations.value = res.data?.data || null
  } catch {
    recommendations.value = null
  } finally {
    recLoading.value = false
  }
}

const actionType = (action?: string) => {
  const m: Record<string, string> = { strong_buy: "success", buy: "warning", watch: "info", review: "danger", avoid: "info" }
  return m[action || ""] || "info"
}

const dimLabel = (key: string | number) => {
  const m: Record<string, string> = { sentiment: "情感", growth: "增长", price: "价格", activity: "活跃" }
  return m[key] || key
}

const dimColor = (score: number) => {
  if (score >= 80) return "#67c23a"
  if (score >= 50) return "#e6a23c"
  return "#f56c6c"
}

const trendColor = (trend: string) => {
  return trend === "up" ? "color: #f56c6c" : trend === "down" ? "color: #67c23a" : "color: #909399"
}

const trendLabel = (trend: string) => {
  return trend === "up" ? "上涨" : trend === "down" ? "下跌" : "稳定"
}

const signalLabel = (sig: string | number) => {
  const m: Record<string, string> = {
    comment_growth_surge: "评论激增",
    sentiment_positive: "好评率高",
    price_stable: "价格稳定",
    recent_activity: "近期活跃",
    comment_velocity: "评论密集",
  }
  return m[sig] || sig
}

const confidenceColor = (confidence: number) => {
  if (confidence >= 70) return "#67c23a"
  if (confidence >= 40) return "#e6a23c"
  return "#f56c6c"
}

const scoreRingStyle = (score: number) => {
  let color = "#f56c6c"
  if (score >= 80) color = "#67c23a"
  else if (score >= 50) color = "#e6a23c"
  return {
    border: `4px solid ${color}`,
    color,
  }
}

onMounted(() => {
  loadUptrend()
  loadCategoryHeat()
  loadRecommendations()
})
</script>
