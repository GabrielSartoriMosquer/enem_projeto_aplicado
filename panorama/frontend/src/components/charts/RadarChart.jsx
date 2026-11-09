const AXES = [
  ['CN', 'Natureza'],
  ['CH', 'Humanas'],
  ['LC', 'Linguagens'],
  ['MT', 'Matemática'],
  ['REDACAO', 'Redação'],
]

function point(index, value, center, radius) {
  const angle = (-Math.PI / 2) + (index * (Math.PI * 2 / AXES.length))
  const distance = (value / 100) * radius
  return [center + Math.cos(angle) * distance, center + Math.sin(angle) * distance]
}

function polygon(points) {
  return points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
}

export default function RadarChart({ results }) {
  const size = 340
  const center = size / 2
  const radius = 112
  const values = AXES.map(([code]) => Number(results.find((item) => item.area === code)?.percentile || 0))
  const userPoints = values.map((value, index) => point(index, value, center, radius))
  const rings = [20, 40, 60, 80, 100]

  return (
    <div className="radar-wrap">
      <svg className="radar-chart" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Radar de percentis do Meu Panorama">
        {rings.map((ring) => (
          <polygon key={ring} className="radar-ring" points={polygon(AXES.map((_, index) => point(index, ring, center, radius)))} />
        ))}
        {AXES.map(([, label], index) => {
          const [x, y] = point(index, 100, center, radius)
          const [tx, ty] = point(index, 123, center, radius)
          return (
            <g key={label}>
              <line className="radar-axis" x1={center} y1={center} x2={x} y2={y} />
              <text className="radar-label" x={tx} y={ty} textAnchor="middle">{label}</text>
            </g>
          )
        })}
        <polygon className="radar-area" points={polygon(userPoints)} />
        {userPoints.map(([x, y], index) => <circle key={AXES[index][0]} className="radar-point" cx={x} cy={y} r="4" />)}
      </svg>
      <p className="chart-note">O radar utiliza percentis para permitir a comparação do posicionamento relativo entre as áreas.</p>
    </div>
  )
}
