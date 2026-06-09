<template>
  <div>
    <h2>用户管理</h2>
    <el-card style="margin-top: 16px">
      <template #header>
        <el-button type="primary" @click="showCreate = true">创建用户</el-button>
      </template>
      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? "正常" : "禁用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>

    <el-dialog v-model="showCreate" title="创建用户" width="400px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createForm.email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" type="password" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { ElMessage } from "element-plus"
import { usersApi } from "@/api"

const loading = ref(false)
const users = ref([])
const showCreate = ref(false)
const createForm = ref({ username: "", email: "", password: "", role: "user" })

const loadUsers = async () => {
  loading.value = true
  try {
    const res = await usersApi.list()
    users.value = res.data.items
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  try {
    await usersApi.create(createForm.value)
    ElMessage.success("创建成功")
    showCreate.value = false
    createForm.value = { username: "", email: "", password: "", role: "user" }
    loadUsers()
  } catch {
    // handled by interceptor
  }
}

onMounted(loadUsers)
</script>
