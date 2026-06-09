import { createRouter, createWebHistory } from "vue-router"
import { useUserStore } from "@/store"

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"),
    meta: { guest: true },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/Register.vue"),
    meta: { guest: true },
  },
  {
    path: "/",
    component: () => import("@/components/layout/AppLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "Dashboard", component: () => import("@/views/Dashboard.vue") },
      { path: "comments", name: "Comments", component: () => import("@/views/Comments.vue") },
      { path: "analysis", name: "AnalysisList", component: () => import("@/views/AnalysisList.vue") },
      { path: "analysis/:taskId", name: "AnalysisResult", component: () => import("@/views/AnalysisResult.vue") },
      { path: "reports", name: "Reports", component: () => import("@/views/Report.vue") },
      { path: "settings", name: "Settings", component: () => import("@/views/Settings.vue") },
      { path: "users", name: "Users", component: () => import("@/views/Users.vue"), meta: { requiresAdmin: true } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const store = useUserStore()
  if (to.meta.requiresAuth && !store.isLoggedIn) {
    next("/login")
  } else if (to.meta.guest && store.isLoggedIn) {
    next("/")
  } else if (to.meta.requiresAdmin && !store.isAdmin) {
    next("/")
  } else {
    next()
  }
})

export default router
