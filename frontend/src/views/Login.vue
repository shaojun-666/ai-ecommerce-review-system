<template>
  <div style="max-width: 400px; margin: 80px auto; padding: 20px">
    <h2 style="text-align: center; margin-bottom: 24px">AI 电商评论分析系统</h2>
    <el-card>
      <template #header><strong>登录</strong></template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名/邮箱" prop="username">
          <el-input v-model="form.username" placeholder="admin / user" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="admin123 / user123" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">登 录</el-button>
        </el-form-item>
        <div style="text-align: center">
          <router-link to="/register" style="color: #409eff; font-size: 14px">注册账号</router-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import { useUserStore } from "@/store"

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const form = reactive({ username: "", password: "" })
const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
}

const handleLogin = async () => {
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success("登录成功")
    router.push("/")
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>
