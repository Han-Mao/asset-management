<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>IT资产全生命周期管理系统</h2>
      <p class="muted">登录后体验：申请领用 → 管理员审批 → 到期提醒 → 归还/维修</p>
      <el-form :model="form" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="账号" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="onSubmit">登录</el-button>
      </el-form>
      <el-divider>演示账号（密码都是 123456）</el-divider>
      <div class="accounts">
        <el-tag v-for="a in accounts" :key="a.username" style="cursor: pointer" @click="fill(a.username)">
          {{ a.username }} · {{ a.role }}
        </el-tag>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '123456' })
const accounts = [
  { username: 'admin', role: '管理员' },
  { username: 'zhangsan', role: '普通用户' },
  { username: 'lisi', role: '普通用户' },
  { username: 'wangwu', role: '普通用户' },
]

function fill(username) {
  form.username = username
  form.password = '123456'
}

async function onSubmit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    await auth.login({ ...form })
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2d3d, #3a6073);
}
.login-card {
  width: 400px;
  padding: 8px;
}
.accounts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
h2 {
  margin: 0 0 6px;
}
</style>
