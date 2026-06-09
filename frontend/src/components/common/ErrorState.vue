<template>
  <div v-if="error" class="error-state" style="padding: 40px; text-align: center">
    <el-result icon="error" title="请求失败" :sub-title="message">
      <template #extra>
        <el-button type="primary" @click="$emit('retry')">重新加载</el-button>
      </template>
    </el-result>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
defineProps<{
  error: boolean
  message?: string
}>()

defineEmits<{
  retry: []
}>()
</script>
