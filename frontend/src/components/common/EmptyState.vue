<template>
  <div v-if="!loading && (!data || data.length === 0)" class="empty-state" style="padding: 40px; text-align: center">
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
}>()

defineEmits<{
  action: []
}>()
</script>
