<template>
  <div v-if="auth.isAdmin">
    <el-row :gutter="16">
      <el-col v-for="card in cards" :key="card.label" :span="4">
        <div class="stat-card">
          <div class="label">{{ card.label }}</div>
          <div class="value" :style="{ color: card.color || '' }">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="4">
        <div class="stat-card">
          <div class="label">待审批</div>
          <div class="value" style="color: #e6a23c">{{ overview.pending_applications }}</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="label">30天内到期</div>
          <div class="value">{{ overview.expiring_30_days }}</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="label">已逾期</div>
          <div class="value" style="color: #f56c6c">{{ overview.overdue_assignments }}</div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="stat-card">
          <div class="label">快捷操作</div>
          <div style="margin-top: 10px; display: flex; gap: 8px">
            <el-button type="primary" @click="router.push('/applications/pending')">去审批</el-button>
            <el-button v-if="auth.hasPerm('asset:create')" @click="router.push('/assets/create')">新增资产</el-button>
            <el-button v-if="auth.hasPerm('asset:export')" @click="exportAll">导出资产</el-button>
            <el-button @click="runReminder">手动触发到期提醒</el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="chart-row" style="margin-top: 16px">
      <Chart :option="statusOption" />
      <Chart :option="categoryOption" />
    </div>

    <el-card style="margin-top: 16px" shadow="never">
      <template #header>未来 30 天到期资产</template>
      <el-table :data="expiry" size="small" empty-text="近期没有到期资产">
        <el-table-column prop="date" label="应归还日期" />
        <el-table-column prop="count" label="台数" />
      </el-table>
    </el-card>
  </div>

  <div v-else>
    <el-row :gutter="16">
      <el-col :span="8">
        <div class="stat-card">
          <div class="label">我的资产</div>
          <div class="value">{{ myAssignments.length }} 台</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card">
          <div class="label">待审批申请</div>
          <div class="value" style="color: #e6a23c">{{ pendingCount }}</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card">
          <div class="label">即将到期（30天内 / 已逾期）</div>
          <div class="value" style="color: #f56c6c">{{ expiringCount }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px" shadow="never">
      <template #header>我的设备</template>
      <el-table :data="myAssignments" empty-text="暂无领用中的设备">
        <el-table-column prop="asset_code" label="资产编号" width="150" />
        <el-table-column prop="asset_name" label="设备" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'OVERDUE' ? 'danger' : 'success'">{{ assignmentLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预计归还" width="130">
          <template #default="{ row }">{{ fmtDate(row.expected_return_time) }}</template>
        </el-table-column>
        <el-table-column label="剩余天数" width="110">
          <template #default="{ row }">
            <span :style="{ color: row.days_left < 0 ? '#f56c6c' : row.days_left <= 7 ? '#e6a23c' : '' }">
              {{ row.days_left < 0 ? `已逾期 ${-row.days_left} 天` : `剩余 ${row.days_left} 天` }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/assets/${row.asset_id}`)">查看</el-button>
            <el-button link type="primary" @click="repair(row)">申请维修</el-button>
            <el-button link type="primary" @click="doReturn(row)">归还</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px" shadow="never">
      <template #header>快捷操作</template>
      <el-button type="primary" @click="router.push('/assets')">申请设备</el-button>
      <el-button @click="router.push('/applications/my')">查看申请</el-button>
      <el-button @click="router.push('/notifications')">查看消息</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Chart from '../components/Chart.vue'
import { api, downloadBlob } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const overview = ref({})
const expiry = ref([])
const statusData = ref([])
const categoryData = ref([])
const myAssignments = ref([])
const myApplications = ref([])

const cards = computed(() => [
  { label: '资产总数', value: overview.value.total_assets ?? 0 },
  { label: '在库', value: overview.value.in_stock ?? 0, color: '#67c23a' },
  { label: '已领用', value: overview.value.borrowed ?? 0, color: '#409eff' },
  { label: '维修中', value: overview.value.repairing ?? 0, color: '#e6a23c' },
  { label: '待报废', value: overview.value.pending_scrap ?? 0 },
  { label: '已报废', value: overview.value.scrapped ?? 0, color: '#909399' },
])

const statusOption = computed(() => ({
  title: { text: '资产状态分布', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      radius: '60%',
      label: { formatter: '{b}: {c}' },
      data: statusData.value.filter((d) => d.count > 0).map((d) => ({ name: d.name, value: d.count })),
    },
  ],
}))

const categoryOption = computed(() => ({
  title: { text: '设备类型统计', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, bottom: 40, top: 50 },
  xAxis: { type: 'category', data: categoryData.value.map((d) => d.name), axisLabel: { rotate: 30 } },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: categoryData.value.map((d) => d.count), itemStyle: { color: '#409eff' } }],
}))

const pendingCount = computed(() => myApplications.value.filter((a) => a.status === 'PENDING').length)
const expiringCount = computed(() => myAssignments.value.filter((a) => a.days_left !== null && a.days_left <= 30).length)

function fmtDate(v) {
  return v ? String(v).slice(0, 10) : '-'
}

const ASSIGNMENT_LABELS = { ACTIVE: '使用中', OVERDUE: '已逾期', RETURNED: '已归还' }

function assignmentLabel(status) {
  return ASSIGNMENT_LABELS[status] || status
}

async function runReminder() {
  const res = await api.triggerReminder()
  ElMessage.success(`提醒任务完成：到期提醒 ${res.expire} 条、逾期提醒 ${res.overdue} 条`)
  auth.refreshUnread()
}

async function exportAll() {
  const resp = await api.exportAssets({})
  downloadBlob(resp, '资产清单.xlsx')
}

async function doReturn(row) {
  await ElMessageBox.confirm(`确认归还 ${row.asset_name} 吗？`, '归还确认')
  await api.returnAssignment(row.id, { remark: '正常归还' })
  ElMessage.success('已归还')
  load()
}

async function repair(row) {
  const { value } = await ElMessageBox.prompt('请描述故障现象', `报修：${row.asset_name}`)
  await api.createRepair({ asset_id: row.asset_id, fault_description: value })
  ElMessage.success('报修已提交')
}

async function load() {
  if (auth.isAdmin) {
    overview.value = await api.overview()
    expiry.value = await api.expiryChart(30)
    statusData.value = await api.assetStatusChart()
    categoryData.value = await api.assetCategoryChart()
  } else {
    // current=true：只取当前持有的设备，已归还的历史记录不进「我的设备」
    myAssignments.value = (await api.myAssignments({ current: true, page_size: 50 })).items
    myApplications.value = (await api.myApplications({ page_size: 50 })).items
  }
}

onMounted(load)
</script>
