export function BarChart({ data, labelKey = 'category', valueKey = 'mean', maxItems = 17 }) {
  const visible = data.slice(0, maxItems)
  const max = Math.max(...visible.map((item) => Number(item[valueKey]) || 0), 1)

  return (
    <div className="bar-chart" role="img" aria-label="Gráfico de barras comparativo">
      {visible.map((item) => {
        const value = Number(item[valueKey]) || 0
        const label = item[labelKey]
        return (
          <div className="bar-row" key={`${label}-${value}`}>
            <div className="bar-meta">
              <span title={label}>{label}</span>
              <strong>{value.toFixed(1)}</strong>
            </div>
            <div className="bar-track" aria-hidden="true">
              <div className="bar-fill" style={{ width: `${Math.max(3, (value / max) * 100)}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
