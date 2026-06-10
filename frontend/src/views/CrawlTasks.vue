<template>
  <div>
    <h2>爬虫管理</h2>

    <!-- Create crawl task -->
    <el-card style="margin-top: 16px">
      <template #header>新建爬虫任务</template>
      <el-form :model="form" label-width="120px" :rules="rules" ref="formRef">
        <el-form-item label="目标 URL" prop="url">
          <el-input v-model="form.url" placeholder="https://item.jd.com/123456.html" style="max-width: 500px" />
        </el-form-item>
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="form.name" placeholder="留空自动使用 URL" style="max-width: 400px" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="form.platform" style="width: 150px" disabled>
            <el-option label="京东" value="jd" />
          </el-select>
        </el-form-item>
        <el-form-item label="抓取页数">
          <el-input-number v-model="form.page_limit" :min="1" :max="100" />
          <span style="margin-left: 8px; color: #999; font-size: 12px">每页约 20-50 条评论</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="creating" @click="createTask">创建任务</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Crawl task list -->
    <el-card style="margin-top: 16px">
      <template #header>
        <span>爬虫任务列表</span>
        <el-tag v-if="stats" style="margin-left: 12px" type="info">
          总计 {{ stats.total }} | 运行中 {{ stats.running }} | 完成 {{ stats.completed }}
        </el-tag>
      </template>

      <div v-if="stats" style="margin-bottom: 16px">
        <el-row :gutter="12">
          <el-col :span="4" v-for="s in statCards" :key="s.label">
            <el-statistic :value="s.value" :title="s.label" />
          </el-col>
        </el-row>
      </div>

      <el-table :data="tasks" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="80" />
        <el-table-column prop="url" label="URL" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <a :href="row.url" target="_blank" style="font-size: 12px">{{ row.url }}</a>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status] || 'info'">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="page_limit" label="页数" width="60" />
        <el-table-column label="发现/新增" width="120">
          <template #default="{ row }">
            <span v-if="row.items_found != null">{{ row.items_found }}/{{ row.items_new }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            <span style="font-size: 12px">{{ row.created_at }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import request from "@/utils/request"

const loading = ref(false)
const creating = ref(false)
const tasks = ref<any[]>([])
const stats = ref<any>(null)
const formRef = ref<any>(null)

const form = reactive({
  url: "",
  name: "",
  platform: "jd",
  page_limit: 5,
})

const rules = {
  url: [
    { required: true, message: "请输入商品 URL", trigger: "blur" },
    { pattern: /^https:\/\/item\.jd\.com\//, message: "请输入有效的京东商品链接 (https://item.jd.com/...)", trigger: "blur" },
  ],
}

const statusMap: Record<string, string> = {
  pending: "info",
  crawling: "warning",
  filtering: "warning",
  completed: "success",
  failed: "danger",
}

const statCards = computed(() => [
  { label: "总计", value: stats.value?.total || 0 },
  { label: "运行中", value: stats.value?.running || 0 },
  { label: "已完成", value: stats.value?.completed || 0 },
  { label: "失败", value: stats.value?.failed || 0 },
  { label: "待处理", value: stats.value?.pending || 0 },
  { label: "采集总量", value: stats.value?.total_items_collected || 0 },
])

const canStart = (status: string) => ["pending", "failed"].includes(status)

const fetchStats = async () => {
  try {
    const res = await request.get("/crawl/stats")
    stats.value = res.data
  } catch {
    // handled
  }
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const res = await request.get("/crawl/tasks")
    tasks.value = res.data?.data || []
  } catch {
    tasks.value = []
  } finally {
    loading.value = false
  }
}

const createTask = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  try {
    await request.post("/crawl/tasks", {
      url: form.url,
      name: form.name || undefined,
      platform: form.platform,
      page_limit: form.page_limit,
    })
    ElMessage.success("爬虫任务已创建")
    form.url = ""
    form.name = ""
    await fetchTasks()
    await fetchStats()
  } catch {
    // handled by interceptor
  } finally {
    creating.value = false
  }
}

const startTask = async (id: number) => {
  try {
    await request.post(`/crawl/tasks/${id}/start`)
    ElMessage.success("任务已启动")
    await fetchTasks()
  } catch {
    // handled
  }
}

const deleteTask = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除该爬虫任务吗？", "确认删除")
    await request.delete(`/crawl/tasks/${id}`)
    ElMessage.success("已删除")
    await fetchTasks()
    await fetchStats()
  } catch {
    // cancelled or error
  }
}

onMounted(async () => {
  await Promise.all([fetchTasks(), fetchStats()])
})
</script>
