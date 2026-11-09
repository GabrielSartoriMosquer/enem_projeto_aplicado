export default function Loading({ label = 'Carregando dados…' }) {
  return (
    <div className="loading-shell" role="status" aria-live="polite">
      <div className="skeleton-card shimmer" />
      <div className="skeleton-card shimmer" />
      <div className="skeleton-card shimmer" />
      <div className="skeleton-card shimmer" />
      <span className="loading-label">{label}</span>
    </div>
  )
}
