import { defineStore } from 'pinia'
import { api } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    roles: JSON.parse(localStorage.getItem('roles') || '[]'),
    permissions: JSON.parse(localStorage.getItem('permissions') || '[]'),
    unreadCount: 0,
  }),
  getters: {
    isAdmin: (s) => s.roles.includes('ADMIN'),
    hasPerm: (s) => (code) => s.permissions.includes(code),
  },
  actions: {
    async login(payload) {
      const data = await api.login(payload)
      this.token = data.access_token
      this.user = { id: data.user.id, username: data.user.username, real_name: data.user.real_name }
      this.roles = data.user.roles
      this.permissions = data.user.permissions
      localStorage.setItem('token', this.token)
      localStorage.setItem('user', JSON.stringify(this.user))
      localStorage.setItem('roles', JSON.stringify(this.roles))
      localStorage.setItem('permissions', JSON.stringify(this.permissions))
      this.refreshUnread()
    },
    async logout() {
      try {
        await api.logout()
      } catch (e) {
        /* 退出失败也要清本地状态 */
      }
      this.clear()
    },
    clear() {
      this.token = ''
      this.user = null
      this.roles = []
      this.permissions = []
      this.unreadCount = 0
      localStorage.clear()
    },
    async refreshUnread() {
      if (!this.token) return
      try {
        const { count } = await api.unreadCount()
        this.unreadCount = count
      } catch (e) {
        this.unreadCount = 0
      }
    },
  },
})
