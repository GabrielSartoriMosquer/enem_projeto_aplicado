export default function StatCard({ icon, label, value, hint, accent }) {
  return (
    <article className="stat-card" data-accent={accent || 'default'}>
      <div className="stat-topline">
        <span className="stat-icon" aria-hidden="true">{icon}</span>
        <span className="stat-label">{label}</span>
      </div>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </article>
  )
}
