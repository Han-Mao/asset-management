import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端统一响应 { code, message, data }：这里直接返回 data，业务错误统一弹消息
const http = axios.create({ baseURL: '/api', timeout: 20000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (resp) => {
    // 文件流（Excel 导出、二维码）直接返回
    if (resp.config.responseType === 'blob' || resp.config.responseType === 'arraybuffer') return resp
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      ElMessage.error(body.message || '操作失败')
      return Promise.reject(new Error(body.message))
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      localStorage.removeItem('token')
      if (location.hash !== '#/login') location.hash = '#/login'
    } else if (status === 403) {
      ElMessage.error(error.response?.data?.message || '没有权限执行该操作')
    } else {
      ElMessage.error(error.response?.data?.message || error.message || '请求失败')
    }
    return Promise.reject(error)
  }
)

export default http

export const api = {
  // 认证
  login: (data) => http.post('/auth/login', data),
  logout: () => http.post('/auth/logout'),
  me: () => http.get('/auth/me'),

  // 资产
  assets: (params) => http.get('/assets', { params }),
  asset: (id) => http.get(`/assets/${id}`),
  createAsset: (data) => http.post('/assets', data),
  updateAsset: (id, data) => http.put(`/assets/${id}`, data),
  deleteAsset: (id) => http.delete(`/assets/${id}`),
  assetStatusOptions: () => http.get('/assets/status-options'),
  pendingScrap: (id) => http.post(`/assets/${id}/pending-scrap`),
  scrapAsset: (id) => http.post(`/assets/${id}/scrap`),
  assetLifecycle: (id) => http.get(`/assets/${id}/lifecycle`),
  assetQrcodeUrl: (id) => `/api/assets/${id}/qrcode`,
  importTemplateUrl: () => '/api/assets/import/template',
  importAssets: (file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/assets/import', form)
  },
  exportAssets: (params) => http.get('/assets/export', { params, responseType: 'blob' }),

  // 分类 / 部门
  categories: () => http.get('/asset-categories'),
  createCategory: (data) => http.post('/asset-categories', data),
  updateCategory: (id, data) => http.put(`/asset-categories/${id}`, data),
  deleteCategory: (id) => http.delete(`/asset-categories/${id}`),
  departments: () => http.get('/departments'),
  createDepartment: (data) => http.post('/departments', data),
  updateDepartment: (id, data) => http.put(`/departments/${id}`, data),
  deleteDepartment: (id) => http.delete(`/departments/${id}`),

  // 申请 / 审批
  applications: (params) => http.get('/applications', { params }),
  myApplications: (params) => http.get('/applications/my', { params }),
  pendingApplications: (params) => http.get('/applications/pending', { params }),
  createApplication: (data) => http.post('/applications', data),
  cancelApplication: (id) => http.post(`/applications/${id}/cancel`),
  approveApplication: (id, remark) => http.post(`/applications/${id}/approve`, { remark }),
  rejectApplication: (id, remark) => http.post(`/applications/${id}/reject`, { remark }),
  batchApprove: (ids, remark) => http.post('/applications/batch-approve', { ids, remark }),

  // 领用 / 归还
  assignments: (params) => http.get('/assignments', { params }),
  myAssignments: (params) => http.get('/assignments/my', { params }),
  returnAssignment: (id, data) => http.post(`/assignments/${id}/return`, data),

  // 维修
  repairs: (params) => http.get('/repairs', { params }),
  createRepair: (data) => http.post('/repairs', data),
  startRepair: (id) => http.post(`/repairs/${id}/start`),
  completeRepair: (id, data) => http.post(`/repairs/${id}/complete`, data),
  cancelRepair: (id) => http.post(`/repairs/${id}/cancel`),
  updateRepair: (id, data) => http.put(`/repairs/${id}`, data),

  // 消息
  notifications: (params) => http.get('/notifications', { params }),
  unreadCount: () => http.get('/notifications/unread-count'),
  readNotification: (id) => http.post(`/notifications/${id}/read`),
  readAllNotifications: () => http.post('/notifications/read-all'),

  // 统计
  overview: () => http.get('/dashboard/overview'),
  assetStatusChart: () => http.get('/dashboard/asset-status'),
  assetCategoryChart: () => http.get('/dashboard/asset-category'),
  departmentChart: () => http.get('/dashboard/department'),
  expiryChart: (days = 30) => http.get('/dashboard/expiry', { params: { days } }),
  borrowTrend: (months = 6) => http.get('/dashboard/borrow-trend', { params: { months } }),
  applicationStats: () => http.get('/dashboard/application-stats'),
  triggerReminder: () => http.post('/system/reminders/test'),

  // 用户 / 角色 / 日志
  users: (params) => http.get('/users', { params }),
  createUser: (data) => http.post('/users', data),
  updateUser: (id, data) => http.put(`/users/${id}`, data),
  deleteUser: (id) => http.delete(`/users/${id}`),
  setUserStatus: (id, status) => http.patch(`/users/${id}/status`, { status }),
  resetPassword: (id, password) => http.post(`/users/${id}/reset-password`, { password }),
  roles: () => http.get('/roles'),
  permissions: () => http.get('/roles/permissions'),
  createRole: (data) => http.post('/roles', data),
  updateRole: (id, data) => http.put(`/roles/${id}`, data),
  deleteRole: (id) => http.delete(`/roles/${id}`),
  logs: (params) => http.get('/operation-logs', { params }),
}

export function downloadBlob(resp, filename) {
  const url = URL.createObjectURL(new Blob([resp.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
