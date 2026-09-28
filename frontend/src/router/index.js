import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '首页' } },
      { path: 'assets', component: () => import('../views/AssetList.vue'), meta: { title: '资产管理' } },
      { path: 'assets/create', component: () => import('../views/AssetForm.vue'), meta: { title: '新增资产', perm: 'asset:create' } },
      { path: 'assets/:id/edit', component: () => import('../views/AssetForm.vue'), meta: { title: '编辑资产', perm: 'asset:update' } },
      { path: 'assets/:id', component: () => import('../views/AssetDetail.vue'), meta: { title: '资产详情' } },
      { path: 'applications/my', component: () => import('../views/MyApplications.vue'), meta: { title: '我的申请' } },
      { path: 'applications/pending', component: () => import('../views/ApprovalCenter.vue'), meta: { title: '审批中心', perm: 'application:approve' } },
      { path: 'assignments/my', component: () => import('../views/MyAssignments.vue'), meta: { title: '我的设备' } },
      { path: 'repairs', component: () => import('../views/Repairs.vue'), meta: { title: '维修管理' } },
      { path: 'notifications', component: () => import('../views/Notifications.vue'), meta: { title: '消息中心' } },
      { path: 'statistics', component: () => import('../views/Statistics.vue'), meta: { title: '统计分析' } },
      { path: 'system', component: () => import('../views/System.vue'), meta: { title: '系统管理', perm: 'user:read' } },
      { path: 'logs', component: () => import('../views/Logs.vue'), meta: { title: '操作日志', perm: 'log:read' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.path === '/login') return true
  if (!auth.token) return '/login'
  // 前端按权限隐藏/拦截，后端仍然会再校验一次
  if (to.meta.perm && !auth.hasPerm(to.meta.perm)) return '/dashboard'
  return true
})

export default router
