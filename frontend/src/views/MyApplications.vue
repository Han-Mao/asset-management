<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-select v-model="status" placeholder="状态" clearable style="width: 140px" @change="load">
        <el-option label="待审批" value="PENDING" />
        <el-option label="已通过" value="APPROVED" />
        <el-option label="已驳回" value="REJECTED" />
        <el-option label="已取消" value="CANCELLED" />
      </el-select>
      <el-button type="primary" @click="router.push('/assets')">去申请设备</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="application_no" label="申请编号" width="170" />
      <el-table-column prop="asset_name" label="设备" min-width="160" />
      <el-table-column prop="asset_code" label="资产编号" width="150" />
      <el-table-column prop="reason" label="使用原因" min-width="140" show-overflow-tooltip />
      <el-table-column label="申请时间" width="130">
        <template #default="{ row }">{{ fmt(row.apply_time) }}</template>
      </el-table-column>
      <el-table-column label="预计归还" width="120">
        <template #default="{ row }">{{ fmt(row.expected_return_time) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status_name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审批意见" min-width="140">
        <template #default="{ row }">{{ row.approval_remark || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'PENDING'" link type="danger" @click="cancel(row)">取消申请</el-button>
        </template>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const status = ref('')
const page = reactive({ page: 1, page_size: 10 })

function fmt(v) {
  return v ? String(v).slice(0, 10) : '-'
}

function statusType(s) {
  return { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', CANCELLED: 'info' }[s]
}

async function load() {
  loading.value = true
  try {
    const data = await api.myApplications({ status: status.value || undefined, page: page.page, page_size: page.page_size })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function cancel(row) {
  await ElMessageBox.confirm(`取消申请 ${row.application_no}？`, '提示')
  await api.cancelApplication(row.id)
  ElMessage.success('已取消')
  load()
}

onMounted(load)
</script>
