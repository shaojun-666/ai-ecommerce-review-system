<template>
  <div v-if="loading" class="skeleton-container" :style="{ padding: type === 'card' ? '0' : '20px' }">
    <template v-if="type === 'card'">
      <el-row :gutter="16">
        <el-col :span="6" v-for="i in count" :key="i">
          <el-card shadow="never">
            <el-skeleton :rows="2" animated />
          </el-card>
        </el-col>
      </el-row>
    </template>
    <template v-else>
      <el-skeleton :rows="rows" animated />
    </template>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  rows?: number
  type?: 'default' | 'card'
  count?: number
}>()
</script>
