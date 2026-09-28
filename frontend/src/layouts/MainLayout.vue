<template>
  <el-container class="layout">
    <el-aside width="210px" class="aside">
      <div class="logo">IT资产管理系统</div>
      <el-menu :default-active="route.path" router background-color="#1f2d3d" text-color="#c0c4cc" active-text-color="#409eff">
        <el-menu-item index="/dashboard">首页</el-menu-item>
        <el-menu-item index="/assets">资产管理</el-menu-item>
        <el-menu-item v-if="auth.hasPerm('asset:create')" index="/assets/create">新增资产</el-menu-item>
        <el-sub-menu index="apply">
          <template #title>领用管理</template>
          <el-menu-item index="/applications/my">我的申请</el-menu-item>
          <el-menu-item v-if="auth.hasPerm('application:approve')" index="/applications/pending">审批中心</el-menu-item>
          <el-menu-item index="/assignments/my">我的设备</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/repairs">维修管理</el-menu-item>
        <el-menu-item index="/notifications">消息中心</el-menu-item>
        <el-menu-item index="/statistics">统计分析</el-menu-item>
        <el-menu-item v-if="auth.hasPerm('user:read')" index="/system">系统管理</el-menu-item>
        <el-menu-item v-if="auth.hasPerm('log:read')" index="/logs">操作日志</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="title">{{ route.meta.title || 'IT资产全生命周期管理系统' }}</div>
        <div class="right">
          <el-badge :value="auth.unreadCount" :hidden="!auth.unreadCount" :max="99">
            <el-button link @click="router.push('/notifications')">消息</el-button>
          </el-badge>
          <el-dropdown @command="onCommand">
            <span class="user">
              {{ auth.user?.real_name || auth.user?.username }}（{{ auth.roles.join('/') }}）
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

onMounted(() => auth.refreshUnread())

async function onCommand(cmd) {
  if (cmd === 'logout') {
    await auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.aside {
  background: #1f2d3d;
}
.logo {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  padding: 18px 16px;
  border-bottom: 1px solid #2c3e50;
}
.aside :deep(.el-menu) {
  border-right: none;
}
.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.right {
  display: flex;
  align-items: center;
  gap: 20px;
}
.user {
  cursor: pointer;
  color: #606266;
}
</style>
