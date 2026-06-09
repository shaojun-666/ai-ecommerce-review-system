<template>
  <div>
    <el-upload
      drag
      :auto-upload="false"
      :show-file-list="true"
      :accept="accept"
      :limit="1"
      @change="handleChange"
    >
      <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
      <div class="el-upload__text">{{ tip }}</div>
      <template #tip>
        <div class="el-upload__tip">{{ fileTip }}</div>
      </template>
    </el-upload>
    <div v-if="result" style="margin-top: 16px">
      <el-alert
        :title="`导入完成: ${result.imported} 成功, ${result.skipped} 跳过`"
        :type="result.errors.length > 0 ? 'warning' : 'success'"
        show-icon
        closable
      />
      <div v-if="result.errors.length > 0" style="margin-top: 8px; max-height: 200px; overflow-y: auto">
        <p v-for="(err, i) in result.errors.slice(0, 20)" :key="i" style="font-size: 12px; color: #e6a23c; margin: 2px 0">
          {{ err }}
        </p>
        <p v-if="result.errors.length > 20" style="font-size: 12px; color: #999">
          ... 还有 {{ result.errors.length - 20 }} 个错误
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { UploadFilled } from "@element-plus/icons-vue"
import { commentsApi } from "@/api"
import { ElMessage } from "element-plus"

defineProps<{
  accept?: string
  tip?: string
  fileTip?: string
}>()

const emit = defineEmits<{
  success: [result: any]
}>()

const result = ref<any>(null)

const handleChange = async (file: any) => {
  if (!file.raw) return
  try {
    const res = await commentsApi.batchImport(file.raw)
    result.value = res.data
    ElMessage.success(`Imported ${res.data?.imported || 0} comments`)
    emit("success", res.data)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.error || "Import failed")
  }
}
</script>
