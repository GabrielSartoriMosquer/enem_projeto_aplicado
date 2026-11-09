export function Loading({ label = 'Carregando dados…' }) {
  return <div className="loading" role="status"><span className="spinner" />{label}</div>
}
