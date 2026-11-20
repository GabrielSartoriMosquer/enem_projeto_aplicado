import { AREAS } from '../../constants/areas'

function point(index, value, center, radius) {
  const angle = (-Math.PI / 2) + (index * (Math.PI * 2 / AREAS.length))
  const distance = (value / 100) * radius
  return [center + Math.cos(angle) * distance, center + Math.sin(angle) * distance]
}

function polygon(points) {
  return points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
}

// Radar dos percentis. Área sem nota (não digitada ou sem dados) não vira "0": fica sem ponto,
// com o rótulo indicando a ausência, e o polígono passa pelo centro.
export default function RadarChart({ results }) {
  const size = 360
  const center = size / 2
  const radius = 116
  const values = AREAS.map(({ code }) => {
    const percentile = results.find((item) => item.area === code)?.percentile
    return percentile === null || percentile === undefined ? null : Number(percentile)
  })
  const userPoints = values.map((value, index) => point(index, value ?? 0, center, radius))
  const rings = [20, 40, 60, 80, 100]

  return (
    <div className="radar-wrap">
      <svg className="radar-chart" viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Radar dos percentis: ${AREAS.map(({ short }, index) => `${short} ${values[index] === null ? 'sem nota' : Math.round(values[index])}`).join(', ')}`}>
        {rings.map((ring) => (
          <polygon key={ring} className="radar-ring" points={polygon(AREAS.map((_, index) => point(index, ring, center, radius)))} />
        ))}
        <polygon className="radar-ring mid" points={polygon(AREAS.map((_, index) => point(index, 50, center, radius)))} />
        {AREAS.map(({ code, short, color }, index) => {
          const [x, y] = point(index, 100, center, radius)
          const [tx, ty] = point(index, 126, center, radius)
          return (
            <g key={code}>
              <line className="radar-axis" x1={center} y1={center} x2={x} y2={y} />
              <text className="radar-label" x={tx} y={ty} textAnchor="middle" fill={color}>{short}</text>
              {values[index] === null && <text className="radar-label missing" x={tx} y={ty + 16} textAnchor="middle">sem nota</text>}
            </g>
          )
        })}
        <polygon className="radar-area" points={polygon(userPoints)} />
        {userPoints.map(([x, y], index) => values[index] !== null && (
          <circle key={AREAS[index].code} className="radar-point" cx={x} cy={y} r="6" fill={AREAS[index].color} />
        ))}
      </svg>
      <p className="chart-note">A linha tracejada marca o meio: metade dos participantes ficou abaixo dela.</p>
    </div>
  )
}
