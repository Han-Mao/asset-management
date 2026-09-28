<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <div class="stat-card">
          <div class="label">{{ c.label }}</div>
          <div class="value">{{ c.value }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="chart-row" style="margin-top: 16px">
      <Chart :option="trendOption" />
      <Chart :option="deptOption" />
    </div>
    <div class="chart-row" style="margin-top: 16px">
      <Chart :option="categoryOption" />
      <Chart :option="applicationOption" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import Chart from '../components/Chart.vue'
import { api } from '../api'

const overview = ref({})
const trend = ref([])
const dept = ref([])
const category = ref([])
const applications = ref([])

const cards = computed(() => [
  { label: '资产总数', value: overview.value.total_assets ?? 0 },
  { label: '在库 / 已领用', value: `${overview.value.in_stock ?? 0} / ${overview.value.borrowed ?? 0}` },
  { label: '维修中 / 待维修', value: `${overview.value.repairing ?? 0} / ${overview.value.pending_repair ?? 0}` },
  { label: '逾期领用', value: overview.value.overdue_assignments ?? 0 },
])

const base = { tooltip: { trigger: 'axis' }, grid: { left: 50, right: 20, bottom: 50, top: 50 } }

const trendOption = computed(() => ({
  title: { text: '月度领用趋势', left: 'center', textStyle: { fontSize: 14 } },
  ...base,
  xAxis: { type: 'category', data: trend.value.map((d) => d.month) },
  yAxis: { type: 'value' },
  series: [{ type: 'line', smooth: true, areaStyle: {}, data: trend.value.map((d) => d.count), itemStyle: { color: '#409eff' } }],
}))

const deptOption = computed(() => ({
  title: { text: '部门资产分布', left: 'center', textStyle: { fontSize: 14 } },
  ...base,
  xAxis: { type: 'category', data: dept.value.map((d) => d.name), axisLabel: { rotate: 20 } },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: dept.value.map((d) => d.count), itemStyle: { color: '#67c23a' } }],
}))

const categoryOption = computed(() => ({
  title: { text: '资产类型分布', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      radius: ['35%', '62%'],
      label: { formatter: '{b}: {c}' },
      data: category.value.map((d) => ({ name: d.name, value: d.count })),
    },
  ],
}))

const applicationOption = computed(() => ({
  title: { text: '申请单状态分布', left: 'center', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      radius: '62%',
      label: { formatter: '{b}: {c}' },
      data: applications.value.map((d) => ({ name: d.name, value: d.count })),
    },
  ],
}))

onMounted(async () => {
  overview.value = await api.overview()
  trend.value = await api.borrowTrend(6)
  dept.value = await api.departmentChart()
  category.value = await api.assetCategoryChart()
  applications.value = await api.applicationStats()
})
</script>
