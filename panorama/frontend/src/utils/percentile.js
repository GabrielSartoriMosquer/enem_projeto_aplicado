export function topPercent(percentile) {
  if (percentile === null || percentile === undefined || Number.isNaN(Number(percentile))) return null
  const value = Math.max(0, Math.min(100, 100 - Number(percentile)))
  return Math.round((value + Number.EPSILON) * 100) / 100
}

export function formatTopPercent(percentile) {
  const value = topPercent(percentile)
  return value === null ? 'Indisponível' : `Top ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
}

export function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Indisponível'
  return Number(value).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
