<template>
  <div v-if="!loading && (!data || data.length === 0)" class="empty-state" style="padding: 40px; text-align: center">
    <div style="font-size: 48px; margin-bottom: 12px">{{ iconMap[type] }}</div>
    <el-empty :description="description">
      <el-button v-if="actionText" type="primary" @click="$emit('action')">
        {{ actionText }}
      </el-button>
    </el-empty>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  data: any[] | null | undefined
  description?: string
  actionText?: string
  type?: 'empty' | 'search' | 'comment' | 'product' | 'data'
}>()

defineEmits<{ action: [] }>()

const iconMap: Record<string, string> = {
  empty: '📭',
  search: '🔍',
  comment: '💬',
  product: '📦',
  data: '📊',
}
</script>
