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

export const formatInteger = (value) => (value === null || value === undefined ? '—' : Math.round(Number(value)).toLocaleString('pt-BR'))

export const formatSigned = (value, digits = 1) => `${value >= 0 ? '+' : '−'}${formatNumber(Math.abs(value), digits)}`

// Quantas das 10 bolinhas do cartão-resposta ficam preenchidas (1 bolinha = 10% dos participantes).
export function filledBubbles(percentile) {
  if (percentile === null || percentile === undefined || Number.isNaN(Number(percentile))) return 0
  return Math.max(0, Math.min(10, Math.round(Number(percentile) / 10)))
}

// O percentil em linguagem do dia a dia. Acima de 90 a frase "melhor que 9 em cada 10" esconde
// a diferença entre 91 e 99, então passa a falar do grupo do topo.
export function percentilePhrase(percentile) {
  if (percentile === null || percentile === undefined || Number.isNaN(Number(percentile))) return 'Sem dados nesta edição'
  const value = Number(percentile)
  if (value >= 99) return 'Entre o 1% com as maiores notas'
  if (value >= 90) return `Entre os ${Math.ceil(100 - value)}% com as maiores notas`
  if (value < 10) return `Melhor que ${Math.max(1, Math.round(value))} em cada 100 participantes`
  return `Melhor que ${Math.round(value / 10)} em cada 10 participantes`
}

// Quantas pessoas tiveram nota maior, arredondado para leitura rápida ("cerca de 329 mil").
export function peopleAhead(percentile, n) {
  if (percentile === null || percentile === undefined || !n) return null
  const ahead = Math.max(0, Math.round(n * (1 - Number(percentile) / 100)))
  if (ahead >= 1_000_000) return `cerca de ${formatNumber(ahead / 1_000_000, 1)} ${ahead >= 2_000_000 ? 'milhões' : 'milhão'}`
  if (ahead >= 10_000) return `cerca de ${Math.round(ahead / 1000).toLocaleString('pt-BR')} mil`
  return ahead.toLocaleString('pt-BR')
}
