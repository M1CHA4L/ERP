export const currencySymbol = 'Tk'
export const currencyCode = 'BDT'

export function formatCurrency(value: number | string | null | undefined) {
  return `${currencySymbol} ${Number(value || 0).toFixed(2)}`
}
