<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button label="PENDING">待审批</el-radio-button>
        <el-radio-button label="APPROVED">已通过</el-radio-button>
        <el-radio-button label="REJECTED">已驳回</el-radio-button>
        <el-radio-button label="">全部</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" placeholder="申请人/设备/编号" style="width: 220px" clearable @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-button v-if="selected.length && status === 'PENDING'" type="success" @click="batch">批量通过（{{ selected.length }}）</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border @selection-change="(v) => (selected = v)">
      <el-table-column type="selection" width="45" v-if="status === 'PENDING'" />
      <el-table-column prop="application_no" label="申请编号" width="170" />
      <el-table-column prop="applicant_name" label="申请人" width="100" />
      <el-table-column prop="department_name" label="部门" width="110" />
      <el-table-column prop="asset_name" label="设备" min-width="150" />
      <el-table-column prop="asset_code" label="资产编号" width="150" />
      <el-table-column prop="reason" label="申请原因" min-width="140" show-overflow-tooltip />
      <el-table-column label="申请时间" width="130">
        <template #default="{ row }">{{ fmt(row.apply_time) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status_name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'PENDING'" link type="primary" @click="open(row)">审批</el-button>
          <span v-else class="muted">{{ row.approver_name || '' }}</span>
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

    <el-dialog v-model="visible" title="领用审批" width="520px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="申请人">{{ current?.applicant_name }}（{{ current?.department_name }}）</el-descriptions-item>
        <el-descriptions-item label="设备">{{ current?.asset_name }} / {{ current?.asset_code }}</el-descriptions-item>
        <el-descriptions-item label="申请理由">{{ current?.reason }}</el-descriptions-item>
        <el-descriptions-item label="预计归还">{{ fmt(current?.expected_return_time) }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="remark" style="margin-top: 12px" placeholder="审批意见（可选）" />
      <template #footer>
        <el-button type="danger" @click="decide(false)">驳回</el-button>
        <el-button type="primary" @click="decide(true)">通过</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const status = ref('PENDING')
const keyword = ref('')
const selected = ref([])
const visible = ref(false)
const current = ref(null)
const remark = ref('')
const page = reactive({ page: 1, page_size: 10 })

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}

function statusType(s) {
  return { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', CANCELLED: 'info' }[s]
}

async function load() {
  loading.value = true
  try {
    const data = await api.applications({ status: status.value || undefined, keyword: keyword.value || undefined, page: page.page, page_size: page.page_size })
    rows.value = data.items
    total.value = data.total
    selected.value = []
  } finally {
    loading.value = false
  }
}

function open(row) {
  current.value = row
  remark.value = '同意领用'
  visible.value = true
}

async function decide(pass) {
  if (pass) await api.approveApplication(current.value.id, remark.value)
  else await api.rejectApplication(current.value.id, remark.value)
  ElMessage.success(pass ? '已通过' : '已驳回')
  visible.value = false
  load()
  auth.refreshUnread()
}

async function batch() {
  await ElMessageBox.confirm(`批量通过 ${selected.value.length} 条申请？`, '批量审批')
  const res = await api.batchApprove(selected.value.map((r) => r.id), '批量通过')
  ElMessage.success(`成功 ${res.success.length} 条，失败 ${res.failed.length} 条`)
  load()
}

onMounted(load)
</script>
