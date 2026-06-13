<template>
  <div>
    <!-- Header -->
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px">
      <h2 style="margin: 0">爬虫管理</h2>
      <div style="display: flex; align-items: center; gap: 12px">
        <el-tag v-if="autoStatus.running" type="success" effect="dark">
          自动采集运行中
        </el-tag>
        <el-tag v-else type="info">自动采集已停止</el-tag>
        <el-button size="small" :loading="refreshing" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <!-- Statistics Cards -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="4" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" :body-style="{ padding: '16px' }">
          <div style="text-align: center">
            <div style="font-size: 28px; font-weight: bold" :style="{ color: card.color }">
              {{ card.value }}
            </div>
            <div style="font-size: 12px; color: #999; margin-top: 4px">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ─── Auto-Crawl Panel ─── -->
    <el-card shadow="hover" style="margin-bottom: 20px; border-left: 4px solid #409EFF">
      <template #header>
        <div style="display: flex; align-items: center; gap: 8px; font-weight: bold">
          <span style="font-size: 18px">🤖</span> 自动采集
          <span style="font-size: 12px; color: #999; font-weight: normal">
            — 一键发现并采集热门商品，无需手动输入链接
          </span>
        </div>
      </template>

      <el-row :gutter="24">
        <!-- Left: Config -->
        <el-col :span="16">
          <el-form label-width="100px" size="small">
            <el-form-item label="采集平台">
              <el-checkbox-group v-model="autoConfig.platforms">
                <el-checkbox label="jd" border>京东</el-checkbox>
                <el-checkbox label="taobao" border>淘宝</el-checkbox>
                <el-checkbox label="pdd" border>拼多多</el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <el-form-item label="商品分类">
              <div style="display: flex; flex-wrap: wrap; gap: 8px; width: 100%">
                <el-checkbox
                  v-for="cat in filteredCategories"
                  :key="cat.name"
                  v-model="autoConfig.selectedCategories"
                  :label="cat.name"
                  border
                  size="small"
                >
                  {{ cat.icon }} {{ cat.name }}
                </el-checkbox>
              </div>
              <div v-if="filteredCategories.length === 0" style="color: #999; font-size: 12px">
                请先选择平台
              </div>
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="每类商品">
                  <el-input-number v-model="autoConfig.maxPerCategory" :min="5" :max="50" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="评论页数">
                  <el-input-number v-model="autoConfig.pageLimit" :min="1" :max="20" size="small" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="间隔(分)">
                  <el-input-number v-model="autoConfig.intervalMinutes" :min="10" :max="240" size="small" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-col>

        <!-- Right: Status + Button -->
        <el-col :span="8" style="display: flex; flex-direction: column; align-items: center; justify-content: center">
          <el-button
            :type="autoStatus.running ? 'danger' : 'primary'"
            size="large"
            :loading="autoLoading"
            style="width: 200px; height: 56px; font-size: 18px"
            @click="toggleAutoCrawl"
          >
            <span v-if="autoStatus.running">⏹ 停止采集</span>
            <span v-else>▶ 开始采集</span>
          </el-button>

          <div v-if="autoStatus.running" style="margin-top: 12px; text-align: center; font-size: 13px; color: #666">
            <div>已运行: {{ autoRunDuration }}</div>
            <div>发现商品: {{ autoStatus.stats?.total_products_found || 0 }}</div>
            <div>创建任务: {{ autoStatus.stats?.total_tasks_created || 0 }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- ─── Task List ─── -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <span style="font-weight: bold">采集任务列表</span>
          <div style="display: flex; gap: 8px">
            <el-select v-model="taskFilter.status" clearable placeholder="状态" size="small" style="width: 120px">
              <el-option label="待处理" value="pending" />
              <el-option label="采集中" value="crawling" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-select v-model="taskFilter.platform" clearable placeholder="平台" size="small" style="width: 100px">
              <el-option label="京东" value="jd" />
              <el-option label="淘宝" value="taobao" />
              <el-option label="拼多多" value="pdd" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="tasks" v-loading="taskLoading" stripe style="width: 100%" empty-text="暂无采集任务">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="70">
          <template #default="{ row }">
            <el-tag :type="platformTag(row.platform)" size="small">{{ row.platform }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status] || 'info'" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="page_limit" label="页数" width="60" />
        <el-table-column label="结果" width="120">
          <template #default="{ row }">
            <span v-if="row.items_found != null" style="font-size: 12px">
              发现 {{ row.items_found }} / 新增 {{ row.items_new }}
            </span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="155">
          <template #default="{ row }">
            <span style="font-size: 12px">{{ row.created_at?.slice(0, 16) || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="startTask(row.id)" :disabled="!canStart(row.status)">
              启动
            </el-button>
            <el-button size="small" type="danger" @click="deleteTask(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ─── Bottom Row: Discovery + Export ─── -->
    <el-row :gutter="20">
      <!-- Discovery results -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between">
              <span style="font-weight: bold">🔍 商品发现</span>
              <el-button size="small" :loading="discovering" @click="manualDiscover">
                手动发现
              </el-button>
            </div>
          </template>
          <div v-if="discoveryResult" style="font-size: 13px">
            <el-tag type="success" size="small" style="margin-right: 8px">完成</el-tag>
            发现 {{ discoveryResult.products_found }} 个商品，
            新增 {{ discoveryResult.products_new }} 个，
            跳过 {{ discoveryResult.products_duplicate }} 个重复，
            创建 {{ discoveryResult.tasks_created }} 个任务
          </div>
          <div v-else style="color: #999; font-size: 13px; text-align: center; padding: 20px">
            点击「手动发现」立即扫描各平台热门分类商品
          </div>
        </el-card>
      </el-col>

      <!-- Data Export -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between">
              <span style="font-weight: bold">💾 数据导出</span>
              <el-button size="small" :loading="exporting" @click="triggerExport">
                立即导出
              </el-button>
            </div>
          </template>

          <div v-if="exports.length" style="max-height: 200px; overflow-y: auto">
            <div v-for="exp in exports" :key="exp.exported_at"
                 style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px">
              <span>{{ exp.exported_at?.slice(0, 19)?.replace('T', ' ') }}</span>
              <span style="color: #666">
                {{ exp.total_products || 0 }} 商品 / {{ exp.total_comments || 0 }} 评论
              </span>
              <span style="color: #999; font-size: 12px">{{ exp.platforms?.join(', ') }}</span>
            </div>
          </div>
          <div v-else style="color: #999; font-size: 13px; text-align: center; padding: 20px">
            暂无导出记录。采集数据后点击「立即导出」
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, reactive } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import request from "@/utils/request"

// ── State ──
const refreshing = ref(false)
const taskLoading = ref(false)
const autoLoading = ref(false)
const discovering = ref(false)
const exporting = ref(false)

const tasks = ref<any[]>([])
const stats = ref<any>({})
const autoStatus = ref<any>({ running: false, stats: {} })
const categories = ref<Record<string, any[]>>({})
const discoveryResult = ref<any>(null)
const exports = ref<any[]>([])
let refreshTimer: number | null = null
let autoRunTimer: number | null = null
const autoRunStart = ref<Date | null>(null)
const autoRunDuration = ref("00:00")

const taskFilter = reactive({
  status: "",
  platform: "",
})

const autoConfig = reactive({
  platforms: ["jd", "taobao", "pdd"] as string[],
  selectedCategories: [] as string[],
  maxPerCategory: 20,
  pageLimit: 3,
  intervalMinutes: 30,
})

// ── Computed ──
const statusMap: Record<string, string> = {
  pending: "info",
  crawling: "warning",
  filtering: "warning",
  completed: "success",
  failed: "danger",
}

const statusLabel = (s: string) => ({
  pending: "待处理", crawling: "采集中", filtering: "过滤中",
  completed: "已完成", failed: "失败",
})[s] || s

const platformTag = (p: string) => ({
  jd: "", taobao: "warning", pdd: "danger",
})[p] || "info"

const filteredCategories = computed(() => {
  const all: any[] = []
  for (const plat of autoConfig.platforms) {
    const platCats = categories.value[plat] || []
    all.push(...platCats)
  }
  return all
})

const statCards = computed(() => [
  { label: "总任务", value: stats.value?.total || 0, color: "#409EFF" },
  { label: "运行中", value: stats.value?.running || 0, color: "#E6A23C" },
  { label: "已完成", value: stats.value?.completed || 0, color: "#67C23A" },
  { label: "失败", value: stats.value?.failed || 0, color: "#F56C6C" },
  { label: "采集总量", value: stats.value?.total_items_collected || 0, color: "#409EFF" },
  { label: "发现商品", value: autoStatus.value?.stats?.total_products_found || 0, color: "#B37FEB" },
])

const canStart = (status: string) => ["pending", "failed"].includes(status)

// ── Duration timer ──
function startDurationTimer() {
  autoRunStart.value = new Date()
  autoRunDuration.value = "00:00"
  autoRunTimer = window.setInterval(() => {
    if (!autoRunStart.value) return
    const diff = Math.floor((Date.now() - autoRunStart.value.getTime()) / 1000)
    const m = String(Math.floor(diff / 60)).padStart(2, "0")
    const s = String(diff % 60).padStart(2, "0")
    autoRunDuration.value = `${m}:${s}`
  }, 1000)
}

function stopDurationTimer() {
  if (autoRunTimer !== null) {
    clearInterval(autoRunTimer)
    autoRunTimer = null
  }
}

// ── API calls ──
async function fetchStats() {
  try {
    const res = await request.get("/crawl/stats")
    stats.value = res.data?.data || {}
    autoStatus.value = {
      running: res.data?.data?.auto_running || false,
      stats: res.data?.data?.auto_stats || {},
      started_at: res.data?.data?.auto_started_at || null,
    }
    if (autoStatus.value.running) {
      if (!autoRunTimer) startDurationTimer()
    } else {
      stopDurationTimer()
    }
  } catch { /* ignore */ }
}

async function fetchTasks() {
  taskLoading.value = true
  try {
    const params: Record<string, string> = {}
    if (taskFilter.status) params.status = taskFilter.status
    if (taskFilter.platform) params.platform = taskFilter.platform
    const res = await request.get("/crawl/tasks", { params })
    tasks.value = res.data?.data || []
  } catch {
    tasks.value = []
  } finally {
    taskLoading.value = false
  }
}

async function fetchCategories() {
  try {
    const res = await request.get("/crawl/discovery/categories")
    categories.value = res.data?.data || {}
  } catch { /* ignore */ }
}

async function fetchExports() {
  try {
    const res = await request.get("/crawl/exports")
    exports.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function refreshAll() {
  refreshing.value = true
  await Promise.all([fetchStats(), fetchTasks(), fetchCategories(), fetchExports()])
  refreshing.value = false
}

// ── Auto-Crawl ──
async function toggleAutoCrawl() {
  autoLoading.value = true
  try {
    if (autoStatus.value.running) {
      await request.post("/crawl/auto/stop")
      ElMessage.success("自动采集已停止")
      stopDurationTimer()
    } else {
      if (autoConfig.platforms.length === 0) {
        ElMessage.warning("请至少选择一个采集平台")
        autoLoading.value = false
        return
      }
      if (autoConfig.selectedCategories.length > 0) {
        ElMessage.info("分类筛选将在服务端按配置的范围进行自动发现")
      }
      await request.post("/crawl/auto/start", {
        platforms: autoConfig.platforms,
        max_per_category: autoConfig.maxPerCategory,
        page_limit: autoConfig.pageLimit,
        interval_minutes: autoConfig.intervalMinutes,
      })
      ElMessage.success("自动采集已启动，后台持续运行中")
      startDurationTimer()
    }
    await fetchStats()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || "操作失败")
  } finally {
    autoLoading.value = false
  }
}

// ── Manual Actions ──
async function manualDiscover() {
  discovering.value = true
  try {
    const res = await request.post("/crawl/discovery/discover", {
      platforms: autoConfig.platforms,
      max_per_category: autoConfig.maxPerCategory,
      auto_start: true,
      page_limit: autoConfig.pageLimit,
    })
    discoveryResult.value = res.data?.data
    ElMessage.success(`发现 ${discoveryResult.value?.products_found || 0} 个商品`)
    await fetchTasks()
    await fetchStats()
  } catch {
    ElMessage.error("发现失败")
  } finally {
    discovering.value = false
  }
}

async function triggerExport() {
  exporting.value = true
  try {
    await request.post("/crawl/exports/export")
    ElMessage.success("数据导出完成")
    await fetchExports()
  } catch {
    ElMessage.error("导出失败")
  } finally {
    exporting.value = false
  }
}

async function startTask(id: number) {
  try {
    await request.post(`/crawl/tasks/${id}/start`)
    ElMessage.success("任务已启动")
    await fetchTasks()
  } catch { /* handled */ }
}

async function deleteTask(id: number) {
  try {
    await ElMessageBox.confirm("确定要删除该爬虫任务吗？", "确认删除")
    await request.delete(`/crawl/tasks/${id}`)
    ElMessage.success("已删除")
    await fetchTasks()
    await fetchStats()
  } catch { /* cancelled or error */ }
}

// ── Lifecycle ──
onMounted(async () => {
  await Promise.all([fetchStats(), fetchTasks(), fetchCategories(), fetchExports()])
  refreshTimer = window.setInterval(() => {
    fetchStats()
  }, 15000)
})

onUnmounted(() => {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  stopDurationTimer()
})
</script>

<style scoped>
.el-form-item {
  margin-bottom: 12px;
}
</style>
