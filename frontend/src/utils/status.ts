export const orderStatusMap: Record<string, string> = {
  draft: '草稿',
  confirmed: '已确认',
  in_production: '生产中',
  pending_inspection: '待检验',
  inspection_passed: '检验通过',
  pending_delivery: '待送货',
  delivered: '已送货',
  pending_payment: '待收款',
  paid: '已结清',
  archived: '已归档',
  cancelled: '已取消',
  paused: '已暂停',
  reworking: '返工中'
}

export const workOrderStatusMap: Record<string, string> = {
  pending_schedule: '待排产',
  scheduled: '已排产',
  in_production: '生产中',
  partial_completed: '部分完成',
  completed: '已完成',
  cancelled: '已取消',
  reworking: '返工中'
}

export const stepStatusMap: Record<string, string> = {
  not_started: '未开始',
  pending_process: '待加工',
  processing: '加工中',
  completed: '已完成',
  pending_inspection: '待检验',
  inspection_passed: '检验通过',
  inspection_failed: '检验失败',
  reworking: '返工中',
  skipped: '已跳过'
}

export function statusLabel(map: Record<string, string>, value: string) {
  return map[value] || value
}
