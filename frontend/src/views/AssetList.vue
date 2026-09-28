<template>
  <div class="page-card">
    <div class="filter-bar">
      <el-input v-model="query.keyword" placeholder="资产编号/名称/序列号" style="width: 220px" clearable />
      <el-select v-model="query.category_id" placeholder="设备类型" style="width: 140px" clearable>
        <el-option v-for="c in categories" :key="c.id" :label="c.category_name" :value="c.id" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" style="width: 130px" clearable>
        <el-option v-for="s in statusOptions" :key="s.status" :label="s.name" :value="s.status" />
      </el-select>
      <el-date-picker v-model="borrowRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="领用开始" end-placeholder="领用结束" style="width: 240px" />
      <el-date-picker v-model="returnRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="应归还开始" end-placeholder="应归还结束" style="width: 260px" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>

    <div style="margin-bottom: 12px; display: flex; gap: 8px">
      <el-button v-if="auth.hasPerm('asset:create')" type="primary" @click="router.push('/assets/create')">新增资产</el-button>
      <el-upload v-if="auth.hasPerm('asset:import')" :show-file-list="false" :before-upload="onImport" accept=".xlsx">
        <el-button>批量导入</el-button>
      </el-upload>
      <el-button v-if="auth.hasPerm('asset:import')" @click="downloadTemplate">下载导入模板</el-button>
      <el-button v-if="auth.hasPerm('asset:export')" @click="onExport">导出</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="asset_code" label="资产编号" width="150" />
      <el-table-column prop="asset_name" label="设备名称" min-width="180" />
      <el-table-column prop="category_name" label="类型" width="90" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ row.status_name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="领用人" width="100">
        <template #default="{ row }">{{ row.borrower_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="预计归还" width="130">
        <template #default="{ row }">
          <span v-if="!row.expected_return_time" class="muted">-</span>
          <span v-else :style="{ color: overdueColor(row) }">
            {{ String(row.expected_return_time).slice(0, 10) }}
            <span v-if="row.days_left < 0" class="muted">（逾期{{ -row.days_left }}天）</span>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="location" label="存放位置" width="110" />
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/assets/${row.id}`)">查看</el-button>
          <el-button v-if="auth.hasPerm('asset:update') && row.status !== 'SCRAPPED'" link type="primary" @click="router.push(`/assets/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="canApply(row)" link type="success" @click="apply(row)">申请领用</el-button>
          <el-button link type="info" @click="showQr(row)">二维码</el-button>
          <el-button v-if="auth.hasPerm('asset:update') && row.status === 'IN_STOCK'" link type="warning" @click="toScrap(row)">待报废</el-button>
          <el-button v-if="auth.hasPerm('asset:delete') && row.status === 'PENDING_SCRAP'" link type="danger" @click="confirmScrap(row)">确认报废</el-button>
          <el-button v-if="auth.hasPerm('asset:delete') && row.status === 'IN_STOCK'" link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      layout="total, sizes, prev, pager, next"
      :total="total"
      v-model:current-page="page.page"
      v-model:page-size="page.page_size"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="load"
      @size-change="search"
    />

    <el-dialog v-model="applyVisible" title="申请领用" width="480px">
      <el-form label-width="90px">
        <el-form-item label="设备">
          <span>{{ current?.asset_name }}（{{ current?.asset_code }}）</span>
        </el-form-item>
        <el-form-item label="使用原因">
          <el-input v-model="applyForm.reason" type="textarea" :rows="3" placeholder="例如：用于项目开发" />
        </el-form-item>
        <el-form-item label="预计归还">
          <el-date-picker v-model="applyForm.expected_return_time" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitApply">提交申请</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="qrVisible" title="资产二维码" width="360px" align-center @closed="releaseQr">
      <div style="text-align: center">
        <img v-if="qrUrl" :src="qrUrl" style="width: 240px; height: 240px" />
        <p class="muted">扫码打开资产详情页（内容是最新数据，需登录）</p>
        <p>{{ current?.asset_code }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, downloadBlob } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const categories = ref([])
const statusOptions = ref([])
const borrowRange = ref([])
const returnRange = ref([])
const applyVisible = ref(false)
const qrVisible = ref(false)
const qrUrl = ref('')
const current = ref(null)
const applyForm = reactive({ reason: '', expected_return_time: '' })
const query = reactive({ keyword: '', category_id: '', status: '' })
const page = reactive({ page: 1, page_size: 20 })

function params() {
  // 清空的下拉框会变成空字符串，必须过滤掉，否则后端按 int 解析会报参数校验失败
  const q = Object.fromEntries(Object.entries({ ...query }).filter(([, v]) => v !== '' && v !== null))
  return {
    ...q,
    borrow_start: borrowRange.value?.[0] ? borrowRange.value[0] + 'T00:00:00' : undefined,
    borrow_end: borrowRange.value?.[1] ? borrowRange.value[1] + 'T23:59:59' : undefined,
    return_start: returnRange.value?.[0] ? returnRange.value[0] + 'T00:00:00' : undefined,
    return_end: returnRange.value?.[1] ? returnRange.value[1] + 'T23:59:59' : undefined,
    page: page.page,
    page_size: page.page_size,
  }
}

async function load() {
  loading.value = true
  try {
    const data = await api.assets(params())
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  page.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.category_id = ''
  query.status = ''
  borrowRange.value = []
  returnRange.value = []
  search()
}

function statusType(status) {
  return {
    IN_STOCK: 'success',
    BORROWED: 'primary',
    PENDING_REPAIR: 'warning',
    REPAIRING: 'warning',
    PENDING_SCRAP: 'info',
    SCRAPPED: 'danger',
  }[status]
}

function overdueColor(row) {
  if (row.days_left === null || row.days_left === undefined) return ''
  if (row.days_left < 0) return '#f56c6c'
  if (row.days_left <= 7) return '#e6a23c'
  return ''
}

function canApply(row) {
  return row.status === 'IN_STOCK' && auth.hasPerm('application:create')
}

function apply(row) {
  current.value = row
  applyForm.reason = ''
  const d = new Date()
  d.setMonth(d.getMonth() + 1)
  applyForm.expected_return_time = d.toISOString().slice(0, 10)
  applyVisible.value = true
}

async function showQr(row) {
  current.value = row
  releaseQr()
  const resp = await api.assetQrcode(row.id)
  qrUrl.value = URL.createObjectURL(resp.data)
  qrVisible.value = true
}

function releaseQr() {
  if (qrUrl.value) {
    URL.revokeObjectURL(qrUrl.value)
    qrUrl.value = ''
  }
}

async function submitApply() {
  if (!applyForm.reason) return ElMessage.warning('请填写使用原因')
  await api.createApplication({
    asset_id: current.value.id,
    reason: applyForm.reason,
    expected_return_time: applyForm.expected_return_time + 'T18:00:00',
  })
  ElMessage.success('申请已提交，等待管理员审批')
  applyVisible.value = false
  load()
}

async function toScrap(row) {
  await ElMessageBox.confirm(`将 ${row.asset_name} 提交为待报废？`, '提示')
  await api.pendingScrap(row.id)
  ElMessage.success('已提交待报废')
  load()
}

async function confirmScrap(row) {
  await ElMessageBox.confirm(`确认报废 ${row.asset_name}？报废后不可再领用。`, '报废确认', { type: 'warning' })
  await api.scrapAsset(row.id)
  ElMessage.success('已报废')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`删除资产 ${row.asset_code}？只有从未使用过的在库资产可以删除。`, '删除确认', { type: 'warning' })
  await api.deleteAsset(row.id)
  ElMessage.success('已删除')
  load()
}

async function onImport(file) {
  const res = await api.importAssets(file)
  ElMessageBox.alert(
    `共 ${res.total} 行：成功 ${res.success}，失败 ${res.failed}` +
      (res.errors.length ? `<br/><br/>` + res.errors.slice(0, 10).map((e) => `第 ${e.row} 行：${e.message}`).join('<br/>') : ''),
    '导入结果',
    { dangerouslyUseHTMLString: true }
  )
  load()
  return false
}

function downloadTemplate() {
  window.open(api.importTemplateUrl())
}

async function onExport() {
  const resp = await api.exportAssets(params())
  downloadBlob(resp, '资产清单.xlsx')
}

onMounted(async () => {
  categories.value = await api.categories()
  statusOptions.value = await api.assetStatusOptions()
  load()
})
</script>
