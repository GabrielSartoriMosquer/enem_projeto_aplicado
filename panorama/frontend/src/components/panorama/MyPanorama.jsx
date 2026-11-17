import { useMemo } from 'react'
import InfoTooltip from '../common/InfoTooltip'
import Loading from '../common/Loading'
import BubbleScale from '../common/BubbleScale'
import RadarChart from '../charts/RadarChart'
import ShareCard from './ShareCard'
import ScoreRangeNote from '../common/ScoreRangeNote'
import { useScoreValidation } from '../../hooks/useScoreRanges'
import { AREAS, AREA_BY_CODE } from '../../constants/areas'
import { formatInteger, formatNumber, formatSigned, peopleAhead, percentilePhrase } from '../../utils/percentile'

const AREA_ORDER = AREAS.map((area) => area.code)

export default function MyPanorama({ year, source, scores, onScoresChange, onSubmit, result, busy, error }) {
  const { ranges, invalid, canSubmit } = useScoreValidation(year, scores)
  const hasAnyScore = Object.values(scores).some((value) => value !== '' && value !== null)

  const submit = (event) => {
    event.preventDefault()
    if (!hasAnyScore || !canSubmit()) return
    onSubmit()
  }

  const results = useMemo(
    () => [...(result?.results || [])].sort((a, b) => AREA_ORDER.indexOf(a.area) - AREA_ORDER.indexOf(b.area)),
    [result],
  )

  const insights = useMemo(() => {
    const available = results.filter((item) => item.percentile !== null)
    if (!available.length) return null
    const best = available.reduce((current, item) => (item.percentile > current.percentile ? item : current))
    const aboveMean = available.filter((item) => item.score > item.mean).length
    // Com menos de 3 áreas o radar vira uma linha solta e não ajuda a comparar.
    return { best, aboveMean, total: available.length, showRadar: available.length >= 3 }
  }, [results])

  return (
    <section id="panorama" className="module-shell panorama-module">
      <div className="section-heading">
        <h2>Onde você ficou no ENEM {year || ''}</h2>
        <p>Digite suas notas. Pode deixar em branco as áreas que não quiser comparar.</p>
      </div>

      <form className="panorama-form" onSubmit={submit} noValidate>
        <div className="panorama-score-grid">
          {AREAS.map(({ code, label, short, color }) => (
            <label className="score-field" key={code} style={{ '--area': color }}>
              <span className="score-field-label"><i className="area-dot" aria-hidden="true" />{short}</span>
              <input
                type="number"
                inputMode="decimal"
                step="0.1"
                placeholder="Sua nota"
                aria-label={`Nota de ${label}`}
                aria-invalid={invalid.includes(code)}
                value={scores[code]}
                onChange={(event) => onScoresChange((current) => ({ ...current, [code]: event.target.value }))}
              />
              <small>{ranges?.[code] ? `de ${Math.ceil(ranges[code].min)} a ${Math.floor(ranges[code].max)}` : ' '}</small>
            </label>
          ))}
        </div>
        <button type="submit" className="button button-primary panorama-submit" disabled={busy || !hasAnyScore}>
          {busy ? 'Calculando…' : 'Ver meu resultado'}
        </button>
      </form>
      <ScoreRangeNote year={year} ranges={ranges} scores={scores} invalid={invalid} labels={Object.fromEntries(AREAS.map((area) => [area.code, area.label]))} />

      {error && <div className="alert" role="alert">{error}</div>}
      {busy && <Loading label="Comparando suas notas com todos os participantes…" />}

      {result && !busy && insights && (
        <div id="panorama-result" className="panorama-result" aria-live="polite">
          {source === 'demo' && (
            <div className="data-source-note"><strong>Dados de demonstração.</strong> Os resultados usam números sintéticos, não os microdados do INEP.</div>
          )}

          <div className="panorama-headline" style={{ '--area': AREA_BY_CODE[insights.best.area]?.color }}>
            <span>Seu melhor resultado foi em {insights.best.label}</span>
            <strong>{percentilePhrase(insights.best.percentile)}</strong>
            <p>
              {insights.aboveMean === insights.total
                ? `Você ficou acima da média ${insights.total > 1 ? `em todas as ${insights.total} áreas` : 'nesta área'} no ENEM ${result.year}.`
                : `Você ficou acima da média em ${insights.aboveMean} de ${insights.total} áreas no ENEM ${result.year}.`}
            </p>
          </div>

          <div className={insights.showRadar ? 'panorama-layout' : 'panorama-layout single'}>
            <ol className="area-results">
              {results.map((item) => {
                const area = AREA_BY_CODE[item.area]
                const ahead = peopleAhead(item.percentile, item.n)
                return (
                  <li className={item.area === insights.best.area ? 'area-result best' : 'area-result'} key={item.area} style={{ '--area': area?.color }}>
                    <div className="area-result-main">
                      <div className="area-result-copy">
                        <h3>{item.label}</h3>
                        <p>{percentilePhrase(item.percentile)}</p>
                      </div>
                      <div className="area-result-scale">
                        <BubbleScale percentile={item.percentile} color={area?.color} label={`Percentil ${formatNumber(item.percentile, 1)}`} />
                        <span className="area-result-percentile">percentil {formatNumber(item.percentile, 1)}</span>
                      </div>
                    </div>
                    <details className="area-details">
                      <summary>Ver números</summary>
                      <dl>
                        <div><dt>Sua nota</dt><dd>{formatNumber(item.score, 1)}</dd></div>
                        <div><dt>Média da edição</dt><dd>{formatNumber(item.mean, 1)}</dd></div>
                        <div><dt>Diferença para a média</dt><dd>{formatSigned(item.score - item.mean)}</dd></div>
                        <div><dt>Pessoas com nota maior</dt><dd>{ahead ?? '—'}</dd></div>
                        <div><dt>Participantes</dt><dd>{formatInteger(item.n)}</dd></div>
                        <div>
                          <dt>Distância da média <InfoTooltip label="Distância da média" text="Também chamada de z-score: quantos desvios-padrão sua nota está acima (positivo) ou abaixo (negativo) da média. Entre −1 e +1 fica a maior parte das pessoas." /></dt>
                          <dd>{item.z_score === null ? '—' : formatSigned(item.z_score, 2)}</dd>
                        </div>
                      </dl>
                    </details>
                  </li>
                )
              })}
            </ol>

            {insights.showRadar && (
              <div className="panorama-radar-panel">
                <h3>Suas áreas lado a lado <InfoTooltip label="Radar" text="Cada ponta mostra o percentil da área, de 0 (centro) a 100 (borda). Quanto mais longe do centro, melhor a posição." /></h3>
                <RadarChart results={results} />
              </div>
            )}
          </div>

          <ShareCard year={result.year} results={results} source={source} />
        </div>
      )}
    </section>
  )
}
