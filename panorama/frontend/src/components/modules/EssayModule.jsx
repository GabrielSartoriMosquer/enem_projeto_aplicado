import { useState } from 'react'
import InfoTooltip from '../common/InfoTooltip'
import { api } from '../../services/api'

export default function EssayModule({ year }) {
  const [score, setScore] = useState(800)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = await api.essay(year, score)
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="module-panel essay-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">MÓDULO 4</span>
          <h2>Posicionamento na redação</h2>
        </div>
        <p>Compare sua nota com a distribuição da mesma edição.</p>
      </div>

      <form className="essay-form" onSubmit={submit}>
        <label className="score-field large">
          <span>Sua nota de redação</span>
          <input
            type="number"
            min="0"
            max="1000"
            step="20"
            value={score}
            onChange={(event) => setScore(Number(event.target.value))}
            aria-label="Nota de redação"
          />
        </label>

        <button type="submit" className="button button-primary" disabled={busy}>
          {busy ? 'Calculando…' : 'Analisar redação'}
        </button>
      </form>

      {error && <div className="alert" role="alert">{error}</div>}

      {result && (
        <div className="essay-result">
          <div className="essay-score-card">
            <span className="mini-label">Nota do usuário</span>
            <strong>{Number(result.score).toFixed(0)}</strong>
          </div>

          <div className="essay-summary">
            <div className="result-kpi">
              <span>Percentil <InfoTooltip label="Percentil" text="A porcentagem de participantes com nota menor ou igual à sua." /></span>
              <strong>{Number(result.percentile).toFixed(2)}%</strong>
            </div>
            <div className="result-kpi">
              <span>Z-score <InfoTooltip label="Z-score" text="Quantos desvios-padrão sua nota está acima ou abaixo da média da edição." /></span>
              <strong>{result.z_score !== null ? Number(result.z_score).toFixed(2) : '—'}</strong>
            </div>
            <div className="result-kpi">
              <span>Média</span>
              <strong>{Number(result.mean).toFixed(1)}</strong>
            </div>
          </div>

          <p className="essay-text">
            Seu resultado está acima de aproximadamente {Number(result.percentile).toFixed(2)}% dos participantes desta edição.
          </p>
        </div>
      )}
    </div>
  )
}
