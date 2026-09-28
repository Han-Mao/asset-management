<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-radio-group v-model="onlyUnread" @change="load">
        <el-radio-button :label="false">全部</el-radio-button>
        <el-radio-button :label="true">未读</el-radio-button>
      </el-radio-group>
      <el-button @click="readAll">全部标记已读</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border @row-click="onRowClick" style="cursor: pointer">
      <el-table-column width="60">
        <template #default="{ row }">
          <el-badge is-dot :hidden="row.is_read" />
        </template>
      </el-table-column>
      <el-table-column label="消息" min-width="320">
        <template #default="{ row }">
          <div :style="{ fontWeight: row.is_read ? 400 : 600 }">{{ row.title }}</div>
          <div class="muted">{{ row.content }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="170">
        <template #default="{ row }">
          <el-tag size="small" :type="typeTag(row.notification_type)">{{ row.notification_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, prev, pager, next"
      :total="total"
      v-model:current-page="page.page"
      v-model:page-size="page.page_size"
      @current-change="load"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const onlyUnread = ref(false)
const page = reactive({ page: 1, page_size: 10 })

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}

function typeTag(type) {
  if (type.includes('REJECT') || type.includes('OVERDUE')) return 'danger'
  if (type.includes('EXPIRE')) return 'warning'
  if (type.includes('APPROVED') || type.includes('COMPLETED')) return 'success'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await api.notifications({ unread: onlyUnread.value, page: page.page, page_size: page.page_size })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
  auth.refreshUnread()
}

async function onRowClick(row) {
  if (row.is_read) return
  await api.readNotification(row.id)
  row.is_read = true
  auth.refreshUnread()
}

async function readAll() {
  await api.readAllNotifications()
  ElMessage.success('已全部标记为已读')
  load()
}

onMounted(load)
</script>
