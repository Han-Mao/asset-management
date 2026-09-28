<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="ACTIVE">领用中</el-radio-button>
        <el-radio-button label="OVERDUE">已逾期</el-radio-button>
        <el-radio-button label="RETURNED">已归还</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="asset_code" label="资产编号" width="150" />
      <el-table-column prop="asset_name" label="设备" min-width="170" />
      <el-table-column label="领用时间" width="120">
        <template #default="{ row }">{{ fmt(row.assign_time) }}</template>
      </el-table-column>
      <el-table-column label="应归还" width="120">
        <template #default="{ row }">{{ fmt(row.expected_return_time) }}</template>
      </el-table-column>
      <el-table-column label="剩余" width="120">
        <template #default="{ row }">
          <span v-if="row.days_left === null" class="muted">-</span>
          <span v-else :style="{ color: row.days_left < 0 ? '#f56c6c' : row.days_left <= 7 ? '#e6a23c' : '' }">
            {{ row.days_left < 0 ? `逾期 ${-row.days_left} 天` : `${row.days_left} 天` }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="{ ACTIVE: 'success', OVERDUE: 'danger', RETURNED: 'info' }[row.status]">
            {{ { ACTIVE: '领用中', OVERDUE: '已逾期', RETURNED: '已归还' }[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/assets/${row.asset_id}`)">查看</el-button>
          <el-button v-if="row.status !== 'RETURNED'" link type="primary" @click="doReturn(row)">归还</el-button>
          <el-button v-if="row.status !== 'RETURNED'" link type="warning" @click="repair(row)">报修</el-button>
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

async function load() {
  loading.value = true
  try {
    const data = await api.myAssignments({ status: status.value || undefined, page: page.page, page_size: page.page_size })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function doReturn(row) {
  const { value } = await ElMessageBox.prompt('归还备注（如“设备完好归还”）', `归还 ${row.asset_name}`, {
    inputValue: '设备完好归还',
    inputValidator: () => true,
  })
  await api.returnAssignment(row.id, { remark: value })
  ElMessage.success('已归还入库')
  load()
}

async function repair(row) {
  const { value } = await ElMessageBox.prompt('请描述故障现象', `报修 ${row.asset_name}`)
  await api.createRepair({ asset_id: row.asset_id, fault_description: value })
  ElMessage.success('报修已提交')
}

onMounted(load)
</script>
