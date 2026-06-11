<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center">
      <h2>告警中心</h2>
      <div>
        <el-button size="small" @click="runChecks" :loading="checking">执行检查</el-button>
        <el-button size="small" @click="markAllRead" v-if="hasUnread">全部标为已读</el-button>
        <el-button size="small" :loading="loading" @click="loadAlerts" style="margin-left: 8px">刷新</el-button>
      </div>
    </div>

    <!-- Severity filter tabs -->
    <el-tabs v-model="filterType" style="margin-top: 16px">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="未读" name="unread" />
    </el-tabs>

    <!-- Alert list -->
    <div v-if="alerts.length" style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px">
      <el-card
        v-for="alert in alerts"
        :key="alert.id"
        :shadow="alert.is_read ? 'never' : 'hover'"
        :style="{ opacity: alert.is_read ? 0.7 : 1 }"
      >
        <div style="display: flex; align-items: flex-start; gap: 12px">
          <el-tag :type="severityType(alert.severity)" size="small" style="margin-top: 2px; flex-shrink: 0">
            {{ severityLabel(alert.severity) }}
          </el-tag>
          <div style="flex: 1; min-width: 0">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <strong :style="alert.is_read ? '' : 'color: #409eff'">{{ alert.title }}</strong>
              <div style="display: flex; align-items: center; gap: 8px">
                <span style="font-size: 12px; color: #999">{{ formatTime(alert.created_at) }}</span>
                <el-button
                  v-if="!alert.is_read"
                  text
                  size="small"
                  type="primary"
                  @click="markRead(alert.id)"
                >标为已读</el-button>
              </div>
            </div>
            <div style="font-size: 13px; color: #666; margin-top: 4px">{{ alert.message }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- Empty state -->
    <div v-else style="text-align: center; padding: 60px 0; color: #999">
      {{ loading ? '加载中...' : '暂无告警' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import request from "@/utils/request"

const loading = ref(false)
const checking = ref(false)
const alerts = ref<any[]>([])
const filterType = ref("all")

const hasUnread = computed(() => alerts.value.some((a: any) => !a.is_read))

const loadAlerts = async () => {
  loading.value = true
  try {
    const params = filterType.value === "unread" ? { unread_only: true } : {}
    const res = await request.get("/alerts", { params })
    alerts.value = res.data?.data || []
  } catch {
    alerts.value = []
  } finally {
    loading.value = false
  }
}

const runChecks = async () => {
  checking.value = true
  try {
    await request.post("/alerts/check")
    await loadAlerts()
  } catch {
    // ignore
  } finally {
    checking.value = false
  }
}

const markRead = async (id: number) => {
  try {
    await request.post(`/alerts/${id}/read`)
    await loadAlerts()
  } catch {
    // ignore
  }
}

const markAllRead = async () => {
  try {
    await request.post("/alerts/read-all")
    await loadAlerts()
  } catch {
    // ignore
  }
}

const severityType = (s: string) => {
  const m: Record<string, string> = { critical: "danger", warning: "warning", info: "info" }
  return m[s] || "info"
}

const severityLabel = (s: string) => {
  const m: Record<string, string> = { critical: "严重", warning: "警告", info: "提示" }
  return m[s] || s
}

const formatTime = (t: string) => {
  if (!t) return ""
  const d = new Date(t)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString("zh-CN")
}

onMounted(loadAlerts)
</script>
