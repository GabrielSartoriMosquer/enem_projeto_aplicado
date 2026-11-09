import { useMemo, useState } from 'react'
import InfoTooltip from '../common/InfoTooltip'
import { api } from '../../services/api'

const AREAS = [
  ['CN', 'Ciências da Natureza'],
  ['CH', 'Ciências Humanas'],
  ['LC', 'Linguagens e Códigos'],
  ['MT', 'Matemática'],
]

export default function PercentileModule({ year }) {
  const [scores, setScores] = useState({ CN: 600, CH: 600, LC: 600, MT: 600 })
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = await api.percentile(
        year,
        Object.fromEntries(Object.entries(scores).map(([key, value]) => [key, Number(value)])),
      )
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const userSummary = useMemo(() => {
    if (!result?.results?.length) return null
    const top = result.results.reduce((best, item) => (item.percentile > best.percentile ? item : best), result.results[0])
    return {
      label: top.label,
      percentile: top.percentile,
      z: top.z_score,
      n: top.n,
    }
  }, [result])

  return (
    <div className="module-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">MÓDULO 1</span>
          <h2>Seu percentil por área</h2>
        </div>
        <p>Analise sua posição em cada disciplina dentro da mesma edição selecionada.</p>
      </div>

      <form className="score-form" onSubmit={submit}>
        <div className="score-grid">
          {AREAS.map(([id, label]) => (
            <label className="score-field" key={id}>
              <span>{label}</span>
              <input
                type="number"
                min="0"
                max="1000"
                step="0.1"
                value={scores[id]}
                onChange={(event) => setScores((current) => ({ ...current, [id]: event.target.value }))}
                aria-label={`${label} - nota`}
              />
            </label>
          ))}
        </div>

        <button type="submit" className="button button-primary" disabled={busy}>
          {busy ? 'Calculando…' : 'Calcular posicionamento'}
        </button>
      </form>

      {error && <div className="alert" role="alert">{error}</div>}

      {userSummary && (
        <div className="insight-banner" aria-live="polite">
          <strong>Você está à frente de {userSummary.percentile.toFixed(1)}% dos participantes</strong>
          <span>{userSummary.label} • z-score {userSummary.z !== null ? Number(userSummary.z).toFixed(2) : '—'} • n = {userSummary.n}</span>
        </div>
      )}

      {result && (
        <div className="result-grid">
          {result.results.map((item) => (
            <article className="percentile-card" key={item.area}>
              <div className="percentile-ring" style={{ '--percent': `${Math.max(item.percentile, 2)}%` }}>
                <span>{item.percentile.toFixed(1)}<small>%</small></span>
              </div>

              <div className="percentile-copy">
                <div className="title-line">
                  <h3>{item.label}</h3>
                  <InfoTooltip label="Percentil" text="O percentil mostra a porcentagem de participantes com nota menor ou igual à sua." />
                </div>
                <p>
                  Nota <strong>{Number(item.score).toFixed(1)}</strong> • média {Number(item.mean).toFixed(1)}
                </p>
                <p className="muted">
                  {item.z_score !== null ? `Z-score ${Number(item.z_score).toFixed(2)} • ` : ''}
                  população {item.n.toLocaleString('pt-BR')}
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
