<template>
  <div>
    <h2>评论管理</h2>
    <el-card style="margin-top: 16px">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-input v-model="filters.product_id" placeholder="商品 ID" clearable />
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.platform" placeholder="平台" clearable style="width: 100%">
            <el-option label="全部" value="" />
            <el-option label="京东" value="jd" />
            <el-option label="淘宝" value="taobao" />
            <el-option label="拼多多" value="pdd" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.sentiment" placeholder="情感" clearable style="width: 100%">
            <el-option label="全部" value="" />
            <el-option label="正面" value="positive" />
            <el-option label="负面" value="negative" />
            <el-option label="中性" value="neutral" />
          </el-select>
        </el-col>
        <el-col :span="2">
          <el-button type="primary" @click="loadComments">搜索</el-button>
        </el-col>
        <el-col :span="8" style="text-align: right">
          <el-upload
            :show-file-list="false"
            :http-request="handleUpload"
            accept=".csv,.xlsx,.xls"
          >
            <el-button type="success">导入评论</el-button>
          </el-upload>
        </el-col>
      </el-row>
    </el-card>

    <el-card style="margin-top: 16px">
      <el-table :data="comments" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="product_name" label="商品" width="150" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="80" />
        <el-table-column prop="content" label="评论内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="rating" label="评分" width="60" />
        <el-table-column label="情感" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.analysis" :type="row.analysis.sentiment === 'positive' ? 'success' : row.analysis.sentiment === 'negative' ? 'danger' : 'info'" size="small">
              {{ row.analysis.sentiment }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > perPage"
        v-model:current-page="page"
        :page-size="perPage"
        :total="total"
        layout="prev, pager, next"
        style="margin-top: 16px; justify-content: center"
        @current-change="loadComments"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { commentsApi } from "@/api"

const loading = ref(false)
const comments = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 20

const filters = reactive({
  product_id: "",
  platform: "",
  sentiment: "",
})

const loadComments = async () => {
  loading.value = true
  try {
    const params = { page: page.value, per_page: perPage, ...filters }
    const res = await commentsApi.list(params)
    comments.value = res.data.items
    total.value = res.data.total
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

const handleUpload = async (options: any) => {
  try {
    await commentsApi.batchImport(options.file)
    ElMessage.success("导入成功")
    loadComments()
  } catch {
    // handled by interceptor
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定删除此评论？", "确认")
    await commentsApi.delete(id)
    ElMessage.success("已删除")
    loadComments()
  } catch {
    // cancelled or error
  }
}

onMounted(loadComments)
</script>
