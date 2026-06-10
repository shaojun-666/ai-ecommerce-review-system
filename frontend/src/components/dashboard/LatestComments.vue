<template>
  <div>
    <Loading :loading="loading">
      <EmptyState :loading="false" :data="comments" description="暂无已分析评论">
        <el-table :data="comments" stripe style="width: 100%" size="small">
          <el-table-column label="情感" width="70">
            <template #default="{ row }">
              <el-tag
                :type="row.sentiment === 'positive' ? 'success' : row.sentiment === 'negative' ? 'danger' : 'info'"
                size="small"
              >
                {{ row.sentiment === 'positive' ? '正面' : row.sentiment === 'negative' ? '负面' : '中性' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="评论内容" min-width="200">
            <template #default="{ row }">
              <div style="display: flex; align-items: center; gap: 6px">
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px">
                  {{ row.content }}
                </span>
                <el-tag v-if="row.fake_score && row.fake_score > 0.7" type="danger" size="small" effect="dark">
                  虚假
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="产品" width="120">
            <template #default="{ row }">
              <span style="font-size: 12px; color: #666">{{ row.product_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="80">
            <template #default="{ row }">
              <span style="font-size: 12px; color: #999">{{ row.analyzed_at?.slice(5, 16) || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </EmptyState>
    </Loading>
  </div>
</template>

<script setup lang="ts">
import Loading from "@/components/common/Loading.vue"
import EmptyState from "@/components/common/EmptyState.vue"

defineProps<{
  comments: any[]
  loading: boolean
}>()
</script>
