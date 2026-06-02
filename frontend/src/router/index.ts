import { createRouter, createWebHistory } from 'vue-router'
import { preferredHomePath } from '../data/navigation'
import { hasPermission, session } from '../stores/session'
import AppShell from '../views/AppShell.vue'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/',
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: () => preferredHomePath(session.user)
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('../views/DashboardView.vue'),
          meta: { permission: 'dashboard:view' }
        },
        {
          path: 'customers',
          name: 'customers',
          component: () => import('../views/CustomersView.vue'),
          meta: { permission: 'customer:view' }
        },
        {
          path: 'cylinders',
          name: 'cylinders',
          component: () => import('../views/CylinderLedgerView.vue'),
          meta: { permission: 'cylinder:view' }
        },
        {
          path: 'products',
          name: 'products',
          component: () => import('../views/ProductsView.vue'),
          meta: { permission: 'product:view' }
        },
        {
          path: 'orders',
          name: 'orders',
          component: () => import('../views/OrdersView.vue'),
          meta: { permission: 'order:view' }
        },
        {
          path: 'orders/:id',
          name: 'order-detail',
          component: () => import('../views/OrderDetailView.vue'),
          meta: { permission: 'order:view' }
        },
        {
          path: 'orders/:id/entrust',
          name: 'order-entrust',
          component: () => import('../views/OrderEntrustView.vue'),
          meta: { permission: 'order:view' }
        },
        {
          path: 'process-routes',
          name: 'process-routes',
          component: () => import('../views/ProcessRoutesView.vue'),
          meta: { permission: 'route:view' }
        },
        {
          path: 'work-orders',
          name: 'work-orders',
          component: () => import('../views/WorkOrdersView.vue'),
          meta: { permission: 'work_order:view', roles: ['admin', 'boss', 'sales', 'designer', 'production_manager', 'inspector'] }
        },
        {
          path: 'work-orders/:id',
          name: 'work-order-detail',
          component: () => import('../views/WorkOrderDetailView.vue'),
          meta: { permission: 'work_order:view' }
        },
        {
          path: 'production-board',
          name: 'production-board',
          component: () => import('../views/ProductionBoardView.vue'),
          meta: { permission: 'work_order:view', roles: ['admin', 'boss', 'production_manager'] }
        },
        {
          path: 'my-tasks',
          name: 'my-tasks',
          component: () => import('../views/MyTasksView.vue'),
          meta: { permission: 'step:report' }
        },
        {
          path: 'inspections',
          name: 'inspections',
          component: () => import('../views/InspectionsView.vue'),
          meta: { permission: 'inspection:view' }
        },
        {
          path: 'deliveries',
          name: 'deliveries',
          component: () => import('../views/DeliveriesView.vue'),
          meta: { permission: 'delivery:view' }
        },
        {
          path: 'inventory',
          name: 'inventory',
          component: () => import('../views/InventoryView.vue'),
          meta: { permission: 'inventory:view' }
        },
        {
          path: 'finance',
          name: 'finance',
          component: () => import('../views/FinanceView.vue'),
          meta: { permission: 'finance:receivable:view' }
        },
        {
          path: 'receipts',
          name: 'receipts',
          component: () => import('../views/ReceiptsView.vue'),
          meta: { permission: 'finance:receivable:view' }
        },
        {
          path: 'production-notices',
          name: 'production-notices',
          component: () => import('../views/PrintJobsView.vue'),
          meta: { permission: 'order:view', roles: ['admin', 'boss', 'sales', 'designer', 'production_manager'] }
        },
        {
          path: 'print-jobs',
          name: 'print-jobs',
          component: () => import('../views/PrintJobsView.vue'),
          meta: { permission: 'report:view', roles: ['admin', 'boss', 'finance', 'production_manager'] }
        },
        {
          path: 'sales-reports',
          name: 'sales-reports',
          component: () => import('../views/SalesReportsView.vue'),
          meta: { permission: 'report:view', roles: ['admin', 'boss', 'finance', 'sales'] }
        },
        {
          path: 'costs',
          name: 'costs',
          component: () => import('../views/CostProfitView.vue'),
          meta: { permission: 'cost:view' }
        },
        {
          path: 'logs',
          name: 'logs',
          component: () => import('../views/OperationLogsView.vue'),
          meta: { permission: 'log:view' }
        },
        {
          path: 'maintenance',
          name: 'maintenance',
          component: () => import('../views/MaintenanceView.vue'),
          meta: { permission: 'master_data:cleanup' }
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('../views/UserManagementView.vue'),
          meta: { permission: 'system:permission' }
        }
      ]
    }
  ]
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && (!session.token || !session.user)) {
    return '/login'
  }
  const permission = to.meta.permission as string | undefined
  if (permission && !hasPermission(permission)) {
    const homePath = preferredHomePath(session.user)
    return to.path === homePath ? false : homePath
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles?.length && !roles.some((role) => session.user?.roles.includes(role))) {
    const homePath = preferredHomePath(session.user)
    return to.path === homePath ? false : homePath
  }
  return true
})

export default router
