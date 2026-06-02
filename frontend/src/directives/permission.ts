import type { Directive } from 'vue'
import { hasPermission } from '../stores/session'

function applyPermission(el: HTMLElement, code?: string) {
  if (code && !hasPermission(code)) {
    el.parentNode?.removeChild(el)
  }
}

export const permissionDirective: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    applyPermission(el, binding.value)
  },
  updated(el, binding) {
    applyPermission(el, binding.value)
  }
}
