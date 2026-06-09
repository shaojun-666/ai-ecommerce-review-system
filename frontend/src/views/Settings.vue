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
import { ref, reactive } from "vue"
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
