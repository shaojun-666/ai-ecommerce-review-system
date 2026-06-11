<template>
  <el-container style="min-height: 100vh">
    <el-aside width="220px">
      <el-menu
        :default-active="route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        style="height: 100vh"
      >
        <div style="padding: 20px; color: #fff; text-align: center; font-size: 16px; font-weight: bold">
          AI 评论分析
        </div>
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据看板</span>
        </el-menu-item>
        <el-menu-item index="/comments">
          <el-icon><ChatDotRound /></el-icon>
          <span>评论管理</span>
        </el-menu-item>
        <el-menu-item index="/products">
          <el-icon><Goods /></el-icon>
          <span>商品管理</span>
        </el-menu-item>
        <el-menu-item index="/products/compare">
          <el-icon><TrendCharts /></el-icon>
          <span>商品对比</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <el-icon><Monitor /></el-icon>
          <span>分析中心</span>
        </el-menu-item>
        <el-menu-item index="/crawl">
          <el-icon><Refresh /></el-icon>
          <span>爬虫管理</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><Document /></el-icon>
          <span>报告管理</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
        <el-menu-item index="/users" v-if="userStore.isAdmin">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: flex-end; height: 60px; padding: 0 20px">
        <el-dropdown trigger="click">
          <span style="cursor: pointer; display: flex; align-items: center; gap: 8px">
            {{ userStore.user?.username || "User" }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/settings')">系统设置</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main style="background: #f0f2f5; min-height: calc(100vh - 60px)">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router"
import { useUserStore } from "@/store"
import {
  DataAnalysis, ChatDotRound, Monitor, Refresh, Document, Setting, User, ArrowDown, Goods, TrendCharts,
} from "@element-plus/icons-vue"

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const handleLogout = () => {
  userStore.logout()
  router.push("/login")
}
</script>
