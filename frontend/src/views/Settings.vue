<template>
  <div>
    <h2>系统设置</h2>
    <el-tabs style="margin-top: 20px">
      <el-tab-pane label="个人信息">
        <el-form :model="profileForm" label-width="100px" style="max-width: 500px; margin-top: 20px">
          <el-form-item label="用户名">
            <el-input v-model="profileForm.username" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="profileForm.email" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveProfile">保存</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="偏好设置">
        <div style="max-width: 500px; margin-top: 20px">
          <p style="color: #666; margin-bottom: 16px">关注品类将影响首页推荐和选品建议</p>
          <el-checkbox-group v-model="preferredCategories">
            <el-checkbox v-for="cat in allCategories" :key="cat.id" :label="cat.id" :value="cat.id">
              {{ cat.icon }} {{ cat.name }}
            </el-checkbox>
          </el-checkbox-group>
          <p v-if="allCategories.length === 0" style="color: #999; margin: 12px 0">暂无品类数据</p>
          <div style="margin-top: 20px">
            <el-button type="primary" @click="savePreferences">保存偏好</el-button>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="密码修改">
        <el-form :model="passwordForm" label-width="120px" style="max-width: 500px; margin-top: 20px">
          <el-form-item label="当前密码">
            <el-input v-model="passwordForm.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="passwordForm.newPassword" type="password" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="changePassword">修改密码</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"
import request from "@/utils/request"

const userStore = useUserStore()

const profileForm = reactive({
  username: userStore.user?.username || "",
  email: userStore.user?.email || "",
})

const passwordForm = reactive({
  oldPassword: "",
  newPassword: "",
})

// Preferences
const allCategories = ref<any[]>([])
const preferredCategories = ref<number[]>([])

const loadCategories = async () => {
  try {
    const res = await request.get("/categories", { params: { tree: true } })
    // Flatten tree to get leaf categories
    const flat: any[] = []
    const tree = res.data?.data || []
    for (const root of tree) {
      if (root.children) flat.push(...root.children)
      else flat.push(root)
    }
    allCategories.value = flat
  } catch { allCategories.value = [] }
}

const loadPreferences = async () => {
  try {
    const res = await request.get("/users/me/preferences")
    const prefs = res.data?.preferences || {}
    preferredCategories.value = prefs.favored_categories || []
  } catch { /* ignore */ }
}

const savePreferences = async () => {
  try {
    await request.put("/users/me/preferences", { favored_categories: preferredCategories.value })
    ElMessage.success("偏好已保存")
  } catch { /* handled by interceptor */ }
}

onMounted(() => {
  loadCategories()
  loadPreferences()
})

const saveProfile = async () => {
  try {
    await request.put("/users/me", profileForm)
    ElMessage.success("保存成功")
  } catch {
    // handled by interceptor
  }
}

const changePassword = async () => {
  try {
    await request.put("/users/me/password", passwordForm)
    ElMessage.success("密码已修改")
    passwordForm.oldPassword = ""
    passwordForm.newPassword = ""
  } catch {
    // handled by interceptor
  }
}
</script>
