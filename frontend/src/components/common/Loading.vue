<template>
  <div v-if="loading" class="skeleton-container" style="padding: 20px">
    <el-skeleton :rows="rows" animated />
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  rows?: number
}>()
</script>
