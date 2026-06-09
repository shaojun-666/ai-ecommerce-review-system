<template>
  <div class="pagination-wrapper" style="display: flex; justify-content: center; padding: 16px 0">
    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      background
      @update:current-page="$emit('page-change', $event)"
      @update:page-size="$emit('size-change', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  "page-change": [page: number]
  "size-change": [size: number]
}>()

const currentPage = computed({
  get: () => props.page,
  set: (v) => emit("page-change", v),
})

const pageSize = computed({
  get: () => props.pageSize,
  set: (v) => emit("size-change", v),
})
</script>
