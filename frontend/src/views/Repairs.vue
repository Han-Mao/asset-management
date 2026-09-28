<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-radio-group v-model="status" @change="load">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="PENDING">待处理</el-radio-button>
        <el-radio-button label="REPAIRING">维修中</el-radio-button>
        <el-radio-button label="COMPLETED">已完成</el-radio-button>
        <el-radio-button label="CANCELLED">已取消</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" placeholder="维修单号/设备" style="width: 200px" clearable @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="repair_no" label="维修单号" width="170" />
      <el-table-column prop="asset_name" label="设备" min-width="150" />
      <el-table-column prop="asset_code" label="资产编号" width="150" />
      <el-table-column prop="reporter_name" label="报修人" width="90" />
      <el-table-column prop="fault_description" label="故障描述" min-width="140" show-overflow-tooltip />
      <el-table-column label="维修方" width="130">
        <template #default="{ row }">{{ row.repair_company || '-' }}</template>
      </el-table-column>
      <el-table-column label="费用" width="100">
        <template #default="{ row }">{{ row.repair_cost ? `¥${row.repair_cost}` : '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="{ PENDING: 'warning', REPAIRING: 'primary', COMPLETED: 'success', CANCELLED: 'info' }[row.status]">
            {{ row.status_name }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canHandle && row.status === 'PENDING'" link type="primary" @click="start(row)">接单</el-button>
          <el-button v-if="canHandle && row.status === 'REPAIRING'" link type="success" @click="complete(row)">完成</el-button>
          <el-button v-if="canHandle && row.status !== 'COMPLETED' && row.status !== 'CANCELLED'" link type="danger" @click="cancel(row)">取消</el-button>
          <el-button link type="primary" @click="router.push(`/assets/${row.asset_id}`)">查看</el-button>
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

    <el-dialog v-model="visible" title="维修完成" width="460px">
      <el-form label-width="90px">
        <el-form-item label="维修方"><el-input v-model="form.repair_company" /></el-form-item>
        <el-form-item label="维修费用"><el-input-number v-model="form.repair_cost" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="维修结果"><el-input v-model="form.repair_result" type="textarea" :rows="3" placeholder="如：更换主板，已恢复正常" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="submitComplete">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const status = ref('')
const keyword = ref('')
const visible = ref(false)
const current = ref(null)
const form = reactive({ repair_company: '', repair_cost: 0, repair_result: '' })
const page = reactive({ page: 1, page_size: 10 })
const canHandle = computed(() => auth.hasPerm('repair:handle'))

async function load() {
  loading.value = true
  try {
    const data = await api.repairs({ status: status.value || undefined, keyword: keyword.value || undefined, page: page.page, page_size: page.page_size })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function start(row) {
  await ElMessageBox.confirm(`接单 ${row.repair_no}？资产将进入维修中。`, '接单确认')
  await api.startRepair(row.id)
  ElMessage.success('已接单')
  load()
}

function complete(row) {
  current.value = row
  form.repair_company = row.repair_company || ''
  form.repair_cost = row.repair_cost ? Number(row.repair_cost) : 0
  form.repair_result = ''
  visible.value = true
}

async function submitComplete() {
  await api.completeRepair(current.value.id, { ...form })
  ElMessage.success('维修已完成，资产状态已更新')
  visible.value = false
  load()
}

async function cancel(row) {
  await ElMessageBox.confirm('取消该维修单？', '提示')
  await api.cancelRepair(row.id)
  ElMessage.success('已取消')
  load()
}

onMounted(load)
</script>
