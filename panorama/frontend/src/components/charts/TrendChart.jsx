import { useEffect, useState } from 'react'
import { formatNumber } from '../../utils/percentile'

const COMPACT = '(max-width: 560px)'

// No celular o SVG é desenhado mais estreito: com a largura de 720 encolhida para a tela, o texto
// ficaria com uns 6 px.
function useCompact() {
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.matchMedia?.(COMPACT).matches)
  useEffect(() => {
    const query = window.matchMedia?.(COMPACT)
    if (!query) return undefined
    const update = () => setCompact(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return compact
}

// Evolução de um percentual ao longo das edições. Ano sem dado (a pergunta não existia) fica
// sem ponto e quebra a linha, em vez de virar zero. `breaks` marca com uma linha tracejada o ano
// em que a pergunta mudou, para ninguém ler a mudança de texto como mudança real.
export default function TrendChart({ points, breaks = [], selectedYear, label }) {
  const compact = useCompact()
  const width = compact ? 400 : 720
  const height = compact ? 230 : 250
  const left = compact ? 40 : 48
  const right = compact ? 16 : 24
  const y0 = 28
  const bottom = 40
  const values = points.map((point) => point.highlight_pct).filter((value) => value !== null && value !== undefined)
  if (!values.length) return null

  // Escala do zero até um pouco acima do maior valor, arredondada a 10, para a altura dizer o tamanho.
  const max = Math.min(100, Math.max(10, Math.ceil((Math.max(...values) * 1.3) / 10) * 10))
  const ticks = [0, max / 2, max]
  const step = (width - left - right) / Math.max(1, points.length - 1)
  const x = (index) => left + (index * step)
  const y = (value) => y0 + ((1 - (value / max)) * (height - y0 - bottom))

  // Segmentos contínuos (um ano sem dado separa um segmento do outro)
  const segments = []
  let current = []
  points.forEach((point, index) => {
    if (point.highlight_pct === null || point.highlight_pct === undefined) {
      if (current.length) segments.push(current)
      current = []
    } else {
      current.push([x(index), y(point.highlight_pct)])
    }
  })
  if (current.length) segments.push(current)

  const first = points.find((point) => point.highlight_pct !== null && point.highlight_pct !== undefined)
  const last = [...points].reverse().find((point) => point.highlight_pct !== null && point.highlight_pct !== undefined)

  return (
    <svg
      className="trend-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${label}: ${points.map((point) => `${point.year} ${point.highlight_pct === null || point.highlight_pct === undefined ? 'sem dado' : `${formatNumber(point.highlight_pct, 1)}%`}`).join(', ')}`}
    >
      <g className="trend-grid">
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
            <text x={left - 10} y={y(tick) + 4} textAnchor="end">{formatNumber(tick, 0)}%</text>
          </g>
        ))}
      </g>

      {breaks.map((item) => {
        const index = points.findIndex((point) => point.year === item.year)
        if (index < 1) return null
        const bx = x(index) - (step / 2)
        return (
          <g key={item.year} className="trend-break">
            <line x1={bx} x2={bx} y1={y0 - 8} y2={height - bottom} />
            <text x={bx + 6} y={y0 - 12}>pergunta mudou</text>
          </g>
        )
      })}

      {segments.map((segment) => (
        <polyline key={segment[0].join()} className="trend-line" points={segment.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(' ')} />
      ))}

      {points.map((point, index) => {
        const value = point.highlight_pct
        const has = value !== null && value !== undefined
        const isSelected = point.year === selectedYear
        const showLabel = has && (isSelected || point === first || point === last)
        return (
          <g key={point.year}>
            {has && (
              <circle className={isSelected ? 'trend-point selected' : 'trend-point'} cx={x(index)} cy={y(value)} r={isSelected ? 6 : 4.5}>
                <title>{`${point.year}: ${formatNumber(value, 1)}%`}</title>
              </circle>
            )}
            {showLabel && (
              <text className={isSelected ? 'trend-value selected' : 'trend-value'} x={x(index)} y={y(value) - 12} textAnchor="middle">
                {formatNumber(value, 1)}%
              </text>
            )}
            <text className={isSelected ? 'trend-year selected' : 'trend-year'} x={x(index)} y={height - 14} textAnchor="middle">
              {point.year}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
