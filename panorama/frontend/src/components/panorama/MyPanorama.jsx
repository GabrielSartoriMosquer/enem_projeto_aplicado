import { useEffect, useMemo, useState } from 'react'
import InfoTooltip from '../common/InfoTooltip'
import Loading from '../common/Loading'
import RadarChart from '../charts/RadarChart'
import ShareCard from './ShareCard'
import { api } from '../../services/api'
import { formatNumber, formatTopPercent } from '../../utils/percentile'

const AREAS = [
  ['CN', 'Natureza'],
  ['CH', 'Humanas'],
  ['LC', 'Linguagens'],
  ['MT', 'Matemática'],
  ['REDACAO', 'Redação'],
]

export default function MyPanorama({ years, year, source, onYearChange }) {
  const [scores, setScores] = useState({ CN: 600, CH: 600, LC: 600, MT: 600, REDACAO: 800 })
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = await api.percentile(year, Object.fromEntries(Object.entries(scores).map(([key, value]) => [key, Number(value)])))
      setResult(payload)
      requestAnimationFrame(() => document.getElementById('panorama-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const insights = useMemo(() => {
    if (!result?.results?.length) return null
    const available = result.results.filter((item) => item.percentile !== null)
    const best = available.reduce((current, item) => item.percentile > current.percentile ? item : current, available[0])
    const closest = available.reduce((current, item) => Math.abs(item.percentile - 50) < Math.abs(current.percentile - 50) ? item : current, available[0])
    const topTen = available.filter((item) => item.percentile >= 90).length
    const headline = best
      ? `Seu melhor posicionamento relativo foi em ${best.label}, no percentil ${formatNumber(best.percentile, 2)}.`
      : 'Ainda não há dados suficientes para gerar seu panorama.'
    return { best, closest, topTen, headline }
  }, [result])

  return (
    <section id="panorama" className="module-shell panorama-module">
      <div className="section-heading">
        <div>
          <span className="eyebrow">EXPERIÊNCIA PREMIUM</span>
          <h2>Meu Panorama ENEM</h2>
        </div>
        <p>Compare seu posicionamento relativo nas cinco áreas sem misturar notas brutas de disciplinas diferentes.</p>
      </div>

      <form className="panorama-form" onSubmit={submit}>
        <label className="filter-field panorama-year">
          <span>Edição do ENEM</span>
          <select value={year} onChange={(event) => onYearChange(Number(event.target.value))}>
            {years.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <div className="panorama-score-grid">
          {AREAS.map(([code, label]) => (
            <label className="score-field" key={code}>
              <span>{label} <small>{code}</small></span>
              <input type="number" min="0" max="1000" step="0.1" value={scores[code]} onChange={(event) => setScores((current) => ({ ...current, [code]: event.target.value }))} />
            </label>
          ))}
        </div>
        <button type="submit" className="button button-primary panorama-submit" disabled={busy}>{busy ? 'Gerando panorama…' : 'Gerar meu Panorama'}</button>
      </form>

      {error && <div className="alert" role="alert">{error}</div>}
      {busy && <Loading label="Calculando seus posicionamentos relativos…" />}

      {result && !busy && (
        <div id="panorama-result" className="panorama-result">
          <div className="data-source-note"><strong>{source === 'demo' ? 'Dados DEMO' : 'Dados oficiais INEP'}</strong><span>{source === 'demo' ? 'Ambiente de demonstração. Os resultados utilizam dados sintéticos.' : 'Resultados calculados com dados oficiais disponíveis.'}</span></div>
          <div className="panorama-headline"><span className="eyebrow">LEITURA PRINCIPAL</span><strong>{insights.headline}</strong><span>{insights.topTen} de {result.results.length} áreas no top 10% relativo.</span></div>

          <div className="panorama-layout">
            <div className="panorama-kpis">
              {result.results.map((item) => (
                <article className={item.area === insights.best?.area ? 'panorama-kpi best' : 'panorama-kpi'} key={item.area}>
                  <div><span>{item.label}</span>{item.area === insights.best?.area && <b>melhor</b>}</div>
                  <strong>{formatNumber(item.percentile, 2)}<small>%</small></strong>
                  <em>{formatTopPercent(item.percentile)}</em>
                  <p>Média {formatNumber(item.mean)} • diferença {item.score - item.mean >= 0 ? '+' : ''}{formatNumber(item.score - item.mean)}<br />N = {item.n.toLocaleString('pt-BR')} • z-score {item.z_score === null ? 'Indisponível' : formatNumber(item.z_score, 2)}</p>
                </article>
              ))}
            </div>
            <div className="panorama-radar-panel">
              <h3>Posicionamento relativo <InfoTooltip label="Radar" text="Cada eixo representa o percentil da área, em uma escala de 0 a 100." /></h3>
              <RadarChart results={result.results} />
              <p className="radar-summary">Área mais próxima da média: <strong>{insights.closest?.label || 'Indisponível'}</strong>.</p>
            </div>
          </div>
          <ShareCard year={year} results={result.results} source={source} />
        </div>
      )}
    </section>
  )
}
