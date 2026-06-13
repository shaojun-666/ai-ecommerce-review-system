<template>
  <div>
    <h2>商品管理</h2>

    <!-- Toolbar -->
    <el-card style="margin-top: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-input v-model="searchKeyword" placeholder="搜索商品名称" clearable @input="loadProducts" />
        </el-col>
        <el-col :span="4">
          <el-select v-model="platformFilter" placeholder="平台" clearable style="width: 100%" @change="loadProducts">
            <el-option label="京东" value="jd" />
            <el-option label="淘宝" value="taobao" />
            <el-option label="拼多多" value="pdd" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="tagFilter" placeholder="标签筛选" clearable style="width: 100%" @change="loadProducts">
            <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-col>
        <el-col :span="10" style="text-align: right">
          <el-button-group style="margin-right: 12px">
            <el-button :type="viewMode === 'table' ? 'primary' : 'default'" size="small" @click="viewMode = 'table'">
              表格
            </el-button>
            <el-button :type="viewMode === 'card' ? 'primary' : 'default'" size="small" @click="viewMode = 'card'">
              卡片
            </el-button>
          </el-button-group>
          <el-button type="primary" @click="showAddDialog = true">添加商品</el-button>
          <el-button @click="showBatchDialog = true">批量导入</el-button>
          <el-button @click="showTagDialog = true" v-if="userStore.isAdmin">管理标签</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Product card grid -->
    <el-card v-if="viewMode === 'card'" style="margin-top: 16px">
      <div v-loading="loading">
        <el-row :gutter="16" v-if="products.length">
          <el-col :span="6" v-for="p in products" :key="p.id" style="margin-bottom: 16px">
            <el-card shadow="hover" style="cursor: pointer; transition: all 0.2s; height: 100%"
              @click="$router.push(`/products/${p.id}`)"
              @mouseenter="$event.currentTarget.style.transform = 'translateY(-4px)'; $event.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)'"
              @mouseleave="$event.currentTarget.style.transform = 'none'; $event.currentTarget.style.boxShadow = 'none'">
              <div style="text-align: center">
                <div style="font-size: 40px; margin-bottom: 8px">📦</div>
                <div style="font-size: 14px; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="p.name">
                  {{ p.name }}
                </div>
                <el-tag size="small" style="margin-top: 4px">{{ p.platform || '未指定' }}</el-tag>
              </div>
              <el-divider style="margin: 12px 0" />
              <div style="display: flex; justify-content: space-around; text-align: center; font-size: 12px">
                <div>
                  <div style="font-weight: bold; color: #409EFF; font-size: 16px">{{ p.monitoring?.comment_count || 0 }}</div>
                  <div style="color: #999">评论</div>
                </div>
                <div>
                  <div v-if="p.monitoring?.latest_price" style="font-weight: bold; color: #F56C6C; font-size: 16px">¥{{ p.monitoring.latest_price }}</div>
                  <div v-else style="color: #999; font-size: 16px">-</div>
                  <div style="color: #999">价格</div>
                </div>
                <div>
                  <div v-if="p.monitoring?.comment_growth_14d != null" :style="{ fontWeight: 'bold', fontSize: '16px', color: p.monitoring.comment_growth_14d > 0 ? '#F56C6C' : '#67C23A' }">
                    {{ p.monitoring.comment_growth_14d > 0 ? '+' : '' }}{{ p.monitoring.comment_growth_14d }}%
                  </div>
                  <div v-else style="color: #999; font-size: 16px">-</div>
                  <div style="color: #999">增长</div>
                </div>
              </div>
              <div v-if="p.tags?.length" style="margin-top: 8px; text-align: center">
                <el-tag v-for="t in p.tags" :key="t.id" :color="t.color" style="color: #fff; margin: 2px" size="small">{{ t.name }}</el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <EmptyState v-else :loading="loading" :data="products" description="暂无商品数据" />
      </div>
      <el-pagination
        v-if="total > perPage"
        v-model:current-page="page"
        :page-size="perPage"
        :total="total"
        layout="prev, pager, next"
        small
        style="margin-top: 16px; justify-content: center"
        @current-change="loadProducts"
      />
    </el-card>

    <!-- Product table -->
    <el-card v-if="viewMode === 'table'" style="margin-top: 16px">
      <el-table :data="products" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="商品名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.platform || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标签" width="180">
          <template #default="{ row }">
            <el-tag v-for="t in (row.tags || [])" :key="t.id" :color="t.color"
              style="color: #fff; margin: 2px" size="small">{{ t.name }}</el-tag>
            <span v-if="!row.tags?.length" style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="当前价格" width="100">
          <template #default="{ row }">
            <span v-if="row.monitoring?.latest_price" style="font-weight: bold; color: #f56c6c">
              ¥{{ row.monitoring.latest_price }}
            </span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="评论数" width="80">
          <template #default="{ row }">
            {{ row.monitoring?.comment_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="评论增长" width="90">
          <template #default="{ row }">
            <span v-if="row.monitoring?.comment_growth_14d != null" :style="growthStyle(row.monitoring.comment_growth_14d)">
              {{ row.monitoring.comment_growth_14d > 0 ? '+' : '' }}{{ row.monitoring.comment_growth_14d }}%
            </span>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="监控状态" width="160">
          <template #default="{ row }">
            <div v-if="row.monitoring?.crawl_task">
              <el-tag :type="taskStatusType(row.monitoring.crawl_task.status)" size="small">
                {{ taskStatusLabel(row.monitoring.crawl_task.status) }}
              </el-tag>
              <div style="font-size: 12px; color: #999; margin-top: 4px">
                最近: {{ formatTime(row.monitoring.crawl_task.completed_at || row.monitoring.crawl_task.created_at) }}
              </div>
            </div>
            <span v-else style="color: #999">未配置</span>
          </template>
        </el-table-column>
        <el-table-column label="数据新鲜度" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.monitoring?.last_comment_date" :type="freshnessType(row.monitoring.last_comment_date)" size="small">
              {{ freshnessLabel(row.monitoring.last_comment_date) }}
            </el-tag>
            <span v-else style="color: #999">无数据</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editProduct(row)">编辑</el-button>
            <el-button size="small" @click="manageTags(row)">标签</el-button>
            <el-button size="small" @click="showPriceChart(row)" v-if="row.monitoring?.latest_price">价格</el-button>
            <el-button size="small" type="danger" plain @click="deleteProduct(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > perPage"
        v-model:current-page="page"
        :page-size="perPage"
        :total="total"
        layout="prev, pager, next"
        small
        style="margin-top: 16px; justify-content: center"
        @current-change="loadProducts"
      />
    </el-card>

    <!-- Add/Edit dialog -->
    <el-dialog v-model="showAddDialog" :title="editingProduct ? '编辑商品' : '添加商品'" width="520px">
      <el-form :model="productForm" label-width="100px">
        <el-form-item label="商品名称" required>
          <el-input v-model="productForm.name" placeholder="输入商品名称" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="productForm.platform" style="width: 100%">
            <el-option label="京东" value="jd" />
            <el-option label="淘宝" value="taobao" />
            <el-option label="拼多多" value="pdd" />
            <el-option label="" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品 URL">
          <el-input v-model="productForm.url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="图片 URL">
          <el-input v-model="productForm.image_url" placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProduct">保存</el-button>
      </template>
    </el-dialog>

    <!-- Tag management dialog (for a single product) -->
    <el-dialog v-model="showTagAssignDialog" title="管理商品标签" width="400px">
      <div v-if="tagAssignProduct">
        <p style="margin-bottom: 12px; font-weight: bold">{{ tagAssignProduct.name }}</p>
        <el-checkbox-group v-model="selectedTagIds">
          <el-checkbox v-for="t in tags" :key="t.id" :label="t.id" :value="t.id">
            <el-tag :color="t.color" style="color: #fff">{{ t.name }}</el-tag>
          </el-checkbox>
        </el-checkbox-group>
        <p v-if="tags.length === 0" style="color: #999">暂无标签，请先创建</p>
      </div>
      <template #footer>
        <el-button @click="showTagAssignDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingTags" @click="saveTagAssignment">保存</el-button>
      </template>
    </el-dialog>

    <!-- Global tag management dialog -->
    <el-dialog v-model="showTagDialog" title="标签管理" width="500px">
      <div style="margin-bottom: 12px; display: flex; gap: 8px">
        <el-input v-model="newTagName" placeholder="标签名称" style="width: 200px" />
        <el-color-picker v-model="newTagColor" :predefine="['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']" />
        <el-button type="primary" @click="createTag">创建</el-button>
      </div>
      <el-table :data="tags" stripe style="width: 100%">
        <el-table-column label="标签名" min-width="120">
          <template #default="{ row }">
            <el-tag :color="row.color" style="color: #fff">{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain @click="deleteTag(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- Batch import dialog -->
    <el-dialog v-model="showBatchDialog" title="批量导入商品" width="480px">
      <p style="margin-bottom: 12px; color: #666">每行一个商品，格式: 名称,平台,URL</p>
      <el-input
        v-model="batchText"
        type="textarea"
        :rows="8"
        placeholder="商品A,jd,https://...
商品B,taobao,https://..."
      />
      <p v-if="batchPreview" style="margin-top: 8px; color: #999">
        将导入 {{ batchPreview }} 个商品
      </p>
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" :loading="batchLoading" :disabled="!batchText.trim()" @click="batchImport">
          导入
        </el-button>
      </template>
    </el-dialog>

    <!-- Price trend chart dialog -->
    <el-dialog v-model="showPriceDialog" :title="`价格趋势 - ${priceChartProduct?.name || ''}`" width="700px">
      <div v-if="priceChartLoading" style="text-align: center; padding: 40px; color: #999">加载中...</div>
      <div v-else-if="priceChartError" style="text-align: center; padding: 40px; color: #f56c6c">{{ priceChartError }}</div>
      <div v-else>
        <div ref="priceChartRef" style="width: 100%; height: 350px"></div>
        <div v-if="priceChartData?.length" style="margin-top: 12px; font-size: 13px; color: #999; text-align: center">
          共 {{ priceChartData.length }} 条价格记录
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick, watch } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { productsApi } from "@/api"
import request from "@/utils/request"
import { useUserStore } from "@/store"
import EmptyState from "@/components/common/EmptyState.vue"

const userStore = useUserStore()

const loading = ref(false)
const products = ref<any[]>([])
const tags = ref<any[]>([])
const page = ref(1)
const perPage = 20
const total = ref(0)
const searchKeyword = ref("")
const platformFilter = ref("")
const tagFilter = ref<number | undefined>()
const viewMode = ref<"table" | "card">(
  (localStorage.getItem("productViewMode") as "table" | "card") || "card"
)

// Add/Edit
const showAddDialog = ref(false)
const editingProduct = ref<any>(null)
const productForm = ref({ name: "", platform: "", url: "", image_url: "" })
const saving = ref(false)

// Tag assign
const showTagAssignDialog = ref(false)
const tagAssignProduct = ref<any>(null)
const selectedTagIds = ref<number[]>([])
const savingTags = ref(false)

// Tag management
const showTagDialog = ref(false)
const newTagName = ref("")
const newTagColor = ref("#409eff")

// Batch import
const showBatchDialog = ref(false)
const batchText = ref("")
const batchLoading = ref(false)

// Price chart
const showPriceDialog = ref(false)
const priceChartProduct = ref<any>(null)
const priceChartRef = ref<HTMLElement | null>(null)
const priceChartData = ref<any[]>([])
const priceChartLoading = ref(false)
const priceChartError = ref("")
let priceChartInstance: any = null

const growthStyle = (rate: number) => {
  if (rate > 10) return { color: '#f56c6c', fontWeight: 'bold' as const }
  if (rate > 0) return { color: '#e6a23c', fontWeight: 'bold' as const }
  if (rate < -10) return { color: '#67c23a', fontWeight: 'bold' as const }
  return { color: '#909399' }
}

const showPriceChart = async (product: any) => {
  priceChartProduct.value = product
  showPriceDialog.value = true
  priceChartLoading.value = true
  priceChartError.value = ""
  priceChartData.value = []

  try {
    const res = await productsApi.prices(product.id, { days: 90 })
    const data = res.data?.data
    const prices = data?.prices || []
    priceChartData.value = prices

    if (!prices.length) {
      priceChartError.value = "暂无价格数据"
      return
    }

    await nextTick()
    renderPriceChart(prices, data?.current_price)
  } catch {
    priceChartError.value = "加载价格数据失败"
  } finally {
    priceChartLoading.value = false
  }
}

const renderPriceChart = (prices: any[], currentPrice: number | null) => {
  if (!priceChartRef.value) return
  import("echarts").then((echarts) => {
    if (priceChartInstance) priceChartInstance.dispose()
    priceChartInstance = echarts.init(priceChartRef.value!)
    const dates = prices.map((p: any) => {
      const d = new Date(p.recorded_at)
      return `${d.getMonth() + 1}/${d.getDate()}`
    })
    const vals = prices.map((p: any) => p.price)
    priceChartInstance.setOption({
      tooltip: { trigger: 'axis', formatter: (params: any) => { const p = params[0]; return `${p.axisValue}<br/>¥${p.value.toFixed(2)}` } },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { formatter: '¥{value}' }, min: (val: any) => Math.max(0, Math.floor(val.min * 0.95)) },
      grid: { left: 60, right: 20, bottom: 60, top: 20 },
      series: [{
        type: 'line', data: vals, smooth: true, symbol: 'circle', symbolSize: 6,
        lineStyle: { color: '#f56c6c', width: 2 },
        areaStyle: { color: 'rgba(245, 108, 108, 0.1)' },
        itemStyle: { color: '#f56c6c' },
        markLine: currentPrice ? { data: [{ yAxis: currentPrice }], silent: true, lineStyle: { color: '#909399', type: 'dashed' }, label: { formatter: `当前 ¥${currentPrice}`, fontSize: 11 } } : undefined,
      }],
    })
  })
}

watch(showPriceDialog, (v) => {
  if (!v && priceChartInstance) {
    setTimeout(() => { priceChartInstance?.dispose(); priceChartInstance = null }, 300)
  }
})

const batchPreview = computed(() => batchText.value.trim().split("\n").filter((l: string) => l.trim()).length)

onMounted(() => { loadProducts(); loadTags() })

watch(viewMode, (v) => localStorage.setItem("productViewMode", v))

const loadProducts = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, per_page: perPage }
    if (searchKeyword.value) params.q = searchKeyword.value
    if (tagFilter.value) params.tag_id = tagFilter.value
    if (platformFilter.value) params.platform = platformFilter.value
    const res = await productsApi.list(params)
    const d = res.data
    products.value = d?.data?.items || d?.data?.data || d?.data || []
    total.value = d?.data?.meta?.total || d?.meta?.total || 0
  } catch { products.value = [] }
   finally { loading.value = false }
}

const loadTags = async () => {
  try { const res = await request.get("/tags"); tags.value = res.data?.data || [] }
  catch { tags.value = [] }
}

const taskStatusMap: Record<string, string> = { pending: "info", processing: "warning", crawling: "warning", filtering: "warning", completed: "success", failed: "danger" }
const taskStatusType = (s: string) => taskStatusMap[s] || "info"
const taskStatusLabel = (s: string) => { const m: Record<string, string> = { pending: "待处理", crawling: "采集中", filtering: "过滤中", completed: "已完成", failed: "失败" }; return m[s] || s }
const freshnessType = (dateStr: string) => { if (!dateStr) return "info"; const diff = Date.now() - new Date(dateStr).getTime(); const hours = diff / 3600000; if (hours < 24) return "success"; if (hours < 72) return "warning"; return "danger" }
const freshnessLabel = (dateStr: string) => { if (!dateStr) return "未知"; const diff = Date.now() - new Date(dateStr).getTime(); const hours = Math.round(diff / 3600000); if (hours < 1) return "刚刚"; if (hours < 24) return `${hours}小时前`; const days = Math.round(hours / 24); return `${days}天前` }
const formatTime = (s: string) => { if (!s) return "-"; return new Date(s).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) }

const editProduct = (product: any) => {
  editingProduct.value = product
  productForm.value = { name: product.name, platform: product.platform || "", url: product.url || "", image_url: product.image_url || "" }
  showAddDialog.value = true
}

const saveProduct = async () => {
  if (!productForm.value.name.trim()) { ElMessage.warning("请输入商品名称"); return }
  saving.value = true
  try {
    if (editingProduct.value) { await request.put(`/products/${editingProduct.value.id}`, productForm.value); ElMessage.success("商品已更新") }
    else { await request.post("/products", productForm.value); ElMessage.success("商品已创建") }
    showAddDialog.value = false; editingProduct.value = null; productForm.value = { name: "", platform: "", url: "", image_url: "" }; await loadProducts()
  } catch { /* handled */ } finally { saving.value = false }
}

const deleteProduct = async (product: any) => {
  try {
    await ElMessageBox.confirm(`确定删除商品「${product.name}」？相关评论也将被删除。`, "确认删除", { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" })
    await request.delete(`/products/${product.id}`); ElMessage.success("已删除"); await loadProducts()
  } catch { /* cancelled or error */ }
}

const manageTags = (product: any) => { tagAssignProduct.value = product; selectedTagIds.value = (product.tags || []).map((t: any) => t.id); showTagAssignDialog.value = true }
const saveTagAssignment = async () => {
  if (!tagAssignProduct.value) return; savingTags.value = true
  try { await request.put(`/products/${tagAssignProduct.value.id}/tags`, { tag_ids: selectedTagIds.value }); ElMessage.success("标签已更新"); showTagAssignDialog.value = false; await loadProducts() }
  catch { /* handled */ } finally { savingTags.value = false }
}
const createTag = async () => {
  if (!newTagName.value.trim()) return
  try { await request.post("/tags", { name: newTagName.value.trim(), color: newTagColor.value }); ElMessage.success("标签已创建"); newTagName.value = ""; await loadTags() }
  catch { /* handled */ }
}
const deleteTag = async (tag: any) => {
  try { await ElMessageBox.confirm(`确定删除标签「${tag.name}」？`, "确认", { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }); await request.delete(`/tags/${tag.id}`); ElMessage.success("标签已删除"); await loadTags() }
  catch { /* cancelled */ }
}
const batchImport = async () => {
  const lines = batchText.value.trim().split("\n").filter((l: string) => l.trim()); if (!lines.length) return; batchLoading.value = true
  let success = 0; let fail = 0
  for (const line of lines) { const parts = line.split(",").map((s: string) => s.trim()); const name = parts[0]; if (!name) { fail++; continue }; try { await request.post("/products", { name, platform: parts[1] || "", url: parts[2] || "" }); success++ } catch { fail++ } }
  batchLoading.value = false; showBatchDialog.value = false; batchText.value = ""; ElMessage.success(`导入完成: ${success} 成功, ${fail} 失败`); await loadProducts()
}
</script>
