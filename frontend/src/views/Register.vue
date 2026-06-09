<template>
  <div style="max-width: 400px; margin: 60px auto; padding: 20px">
    <h2 style="text-align: center; margin-bottom: 24px">用户注册</h2>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleRegister">
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" placeholder="请输入邮箱" />
      </el-form-item>
      <el-form-item label="密码" prop="password">
        <el-input v-model="form.password" type="password" show-password placeholder="至少6位" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="submitting" style="width: 100%">
          注册
        </el-button>
      </el-form-item>
    </el-form>
    <div style="text-align: center">
      <span style="color: #999">已有账号？</span>
      <router-link to="/login" style="color: #409eff">去登录</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import request from "@/utils/request"

const router = useRouter()
const formRef = ref()
const submitting = ref(false)

const form = reactive({
  username: "",
  email: "",
  password: "",
})

const rules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  email: [{ required: true, message: "请输入邮箱", trigger: "blur" }, { type: "email", message: "邮箱格式不正确", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }, { min: 6, message: "密码至少6位", trigger: "blur" }],
}

const handleRegister = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await request.post("/auth/register", form)
    ElMessage.success("注册成功，请登录")
    router.push("/login")
  } catch {
    // handled by interceptor
  } finally {
    submitting.value = false
  }
}
</script>
