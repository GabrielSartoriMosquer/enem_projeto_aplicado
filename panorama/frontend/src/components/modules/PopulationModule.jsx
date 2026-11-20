import { useEffect, useMemo, useRef, useState } from 'react'
import BrazilMap from '../brazil-map/BrazilMap'
import TrendChart from '../charts/TrendChart'
import InfoTooltip from '../common/InfoTooltip'
import Loading from '../common/Loading'
import { api } from '../../services/api'
import { formatInteger, formatNumber } from '../../utils/percentile'

const pct = (value) => (value === null || value === undefined ? '—' : `${formatNumber(value, 1)}%`)
const DEFAULT_INDICATOR = 'internet'

// Usa sempre a resposta do pedido mais recente: se a pessoa troca de indicador ou de edição
// antes da resposta chegar, a resposta antiga é descartada.
function useRequest(load, deps) {
  const [state, setState] = useState({ data: null, error: '' })
  useEffect(() => {
    if (!load) return undefined
    let current = true
    setState({ data: null, error: '' })
    load()
      .then((data) => { if (current) setState({ data, error: '' }) })
      .catch((err) => { if (current) setState({ data: null, error: err.message }) })
    return () => { current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

// Barras de 0 a 100%. Com `compare`, uma barra fina cinza embaixo mostra o mesmo grupo no Brasil.
function Bars({ categories, compare, compareLabel }) {
  return (
    <ol className="pop-bars">
      {categories.map((category) => {
        const other = compare?.find((item) => item.code === category.code)
        return (
          <li key={category.code} className="pop-bar-row">
            <span className="pop-bar-label">{category.label}</span>
            <span className="pop-bar-track" aria-hidden="true">
              <i className="pop-bar-fill" style={{ width: `${category.pct || 0}%` }} />
              {other && <i className="pop-bar-fill compare" style={{ width: `${other.pct || 0}%` }} />}
            </span>
            <span className="pop-bar-value">
              {pct(category.pct)}
              {other && <small>{compareLabel} {pct(other.pct)}</small>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default function PopulationModule({ year, years = [], onYearChange }) {
  const [indicatorId, setIndicatorId] = useState(DEFAULT_INDICATOR)
  const [themeId, setThemeId] = useState('conectividade')
  const [selectedUf, setSelectedUf] = useState('')
  const [recorte, setRecorte] = useState('renda')
  const explorerRef = useRef(null)

  const catalog = useRequest(() => api.populationCatalog(), [])
  const highlights = useRequest(year ? () => api.populationHighlights(year) : null, [year])
  const indicator = useRequest(year ? () => api.populationIndicator(year, indicatorId) : null, [year, indicatorId])
  const trend = useRequest(() => api.populationTrend(indicatorId), [indicatorId])
  const cross = useRequest(year ? () => api.populationCrosstab(year, indicatorId, recorte) : null, [year, indicatorId, recorte])

  const themes = catalog.data?.themes || []
  const indicators = catalog.data?.indicators || []
  const meta = indicators.find((item) => item.id === indicatorId)
  const themeIndicators = indicators.filter((item) => item.theme === themeId)
  const data = indicator.data
  const availableHere = data?.available !== false

  const chooseIndicator = (id, scroll = false) => {
    const target = indicators.find((item) => item.id === id)
    if (target) setThemeId(target.theme)
    setIndicatorId(id)
    if (scroll) requestAnimationFrame(() => explorerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const chooseTheme = (id) => {
    setThemeId(id)
    const first = indicators.find((item) => item.theme === id)
    if (first) setIndicatorId(first.id)
  }

  const mapStates = useMemo(
    () => (data?.states || []).map((state) => ({ uf: state.uf, name: state.name, mean: state.highlight_pct })),
    [data],
  )
  const extremes = useMemo(() => {
    const ranked = (data?.states || []).filter((state) => state.highlight_pct !== null).sort((a, b) => a.highlight_pct - b.highlight_pct)
    return ranked.length ? { low: ranked[0], high: ranked.at(-1) } : null
  }, [data])
  const selectedState = data?.states?.find((state) => state.uf === selectedUf)
  const indicatorYears = meta?.years || []
  const fallbackYear = [...indicatorYears].sort((a, b) => b - a)[0]

  if (catalog.error) {
    return (
      <div className="module-panel">
        <div className="section-heading"><h2>Quem faz o ENEM</h2></div>
        <div className="map-unavailable" role="status">
          <h3>Esta área não está disponível no momento</h3>
          <p>{catalog.error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="module-panel">
      <div className="section-heading">
        <h2>Quem faz o ENEM</h2>
        <p>
          Um retrato de quem se inscreveu no ENEM {year || ''} a partir do questionário socioeconômico.
          É um recorte dos inscritos, não de toda a população brasileira.
        </p>
      </div>

      {/* Fatos de destaque */}
      {highlights.error && <div className="alert" role="alert">{highlights.error}</div>}
      {!highlights.data ? (!highlights.error && <Loading label="Montando o retrato dos inscritos…" />) : (
        <>
          <p className="pop-lead">
            <strong>{formatInteger(highlights.data.participants)}</strong> pessoas se inscreveram no ENEM {highlights.data.year}. Entre elas:
          </p>
          <ul className="pop-facts">
            {highlights.data.facts.map((fact) => (
              <li key={fact.id}>
                <button type="button" className="pop-fact" onClick={() => chooseIndicator(fact.indicator, true)}>
                  <strong>{pct(fact.value)}</strong>
                  <span className="pop-fact-text">{fact.text}</span>
                  {fact.detail && <span className="pop-fact-detail">{fact.detail}</span>}
                  <span className="pop-fact-link">Ver por estado</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* Explorador por tema */}
      <div className="pop-explorer" ref={explorerRef}>
        <div className="pop-themes" role="tablist" aria-label="Temas do questionário">
          {themes.map((theme) => (
            <button
              key={theme.id}
              type="button"
              role="tab"
              aria-selected={themeId === theme.id}
              className={themeId === theme.id ? 'pop-theme active' : 'pop-theme'}
              onClick={() => chooseTheme(theme.id)}
            >
              {theme.label}
            </button>
          ))}
        </div>
        <div className="pop-indicators" role="group" aria-label="Indicadores do tema">
          {themeIndicators.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={indicatorId === item.id}
              className={indicatorId === item.id ? 'pop-chip active' : 'pop-chip'}
              onClick={() => chooseIndicator(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {meta && (
          <div className="pop-indicator-head">
            <h3>
              {meta.label}
              <InfoTooltip label={meta.label} text={meta.question} />
            </h3>
            {data?.notes?.map((note) => <p key={note} className="pop-note">{note}</p>)}
          </div>
        )}

        {indicator.error && <div className="alert" role="alert">{indicator.error}</div>}
        {!data ? (!indicator.error && <Loading label="Buscando os dados do indicador…" />) : !availableHere ? (
          <div className="map-unavailable" role="status">
            <h3>{meta?.label} não existe no ENEM {year}</h3>
            <p>Esta pergunta só aparece no questionário de {indicatorYears.join(', ')}.</p>
            {fallbackYear && onYearChange && (
              <button type="button" className="button button-primary" onClick={() => onYearChange(fallbackYear)}>Ver o ENEM {fallbackYear}</button>
            )}
          </div>
        ) : (
          <>
            <div className="regional-overview pop-overview">
              <div className="regional-map-card">
                <div className="chart-card-heading">
                  <h3>Inscritos {meta?.highlight_label}</h3>
                  <span className="coverage-badge">Brasil: {pct(data.national.highlight_pct)}</span>
                </div>
                {meta?.map ? (
                  <>
                    <p className="map-hint">Percentual em cada estado. Clique em um estado para comparar com o Brasil.</p>
                    <BrazilMap
                      states={mapStates}
                      selectedUf={selectedUf}
                      onSelect={(uf) => setSelectedUf((current) => (current === uf ? '' : uf))}
                      formatValue={pct}
                      valueLabel={meta.highlight_label.charAt(0).toUpperCase() + meta.highlight_label.slice(1)}
                      description={`Mapa do Brasil com o percentual de inscritos ${meta.highlight_label} por estado`}
                    />
                    {extremes && (
                      <p className="pop-extremes">
                        Maior: <strong>{extremes.high.name}</strong> ({pct(extremes.high.highlight_pct)}) · Menor: <strong>{extremes.low.name}</strong> ({pct(extremes.low.highlight_pct)})
                      </p>
                    )}
                  </>
                ) : (
                  <p className="map-hint">Este indicador não tem leitura por estado; veja a distribuição ao lado.</p>
                )}
              </div>

              <div className="pop-dist-card" aria-live="polite">
                <div className="pop-dist-head">
                  <h3>{selectedState ? `${selectedState.name} e Brasil` : 'Brasil'}</h3>
                  {meta?.map && (
                    <label className="filter-field pop-state-select">
                      <span>Comparar com</span>
                      <select value={selectedUf} onChange={(event) => setSelectedUf(event.target.value)}>
                        <option value="">Só o Brasil</option>
                        {(data.states || []).slice().sort((a, b) => a.name.localeCompare(b.name, 'pt-BR')).map((state) => (
                          <option key={state.uf} value={state.uf}>{state.name}</option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
                {selectedState && (
                  <p className="pop-legend">
                    <i className="pop-swatch" /> {selectedState.name} <i className="pop-swatch compare" /> Brasil
                  </p>
                )}
                <Bars
                  categories={selectedState ? selectedState.categories : data.national.categories}
                  compare={selectedState ? data.national.categories : null}
                  compareLabel="Brasil"
                />
                <p className="pop-total">
                  {formatInteger(selectedState ? selectedState.total : data.national.total)} inscritos responderam
                </p>
              </div>
            </div>

            <div className="pop-lower">
              <div className="ranking-card pop-trend-card">
                <div className="ranking-heading">
                  <div>
                    <h3>Inscritos {meta?.highlight_label}, edição a edição</h3>
                    <p>Percentual no Brasil, de {years[0] || 2018} a {years.at(-1) || 2025}.</p>
                  </div>
                </div>
                {trend.error && <div className="alert" role="alert">{trend.error}</div>}
                {trend.data ? (
                  <>
                    <TrendChart points={trend.data.points} breaks={trend.data.breaks} selectedYear={year} label={`Inscritos ${meta?.highlight_label}`} />
                    {trend.data.breaks.map((item) => <p key={item.year} className="pop-note">{item.text}</p>)}
                  </>
                ) : (!trend.error && <Loading label="Buscando a evolução…" />)}
              </div>

              <div className="ranking-card pop-cross-card">
                <div className="ranking-heading">
                  <div>
                    <h3>Inscritos {meta?.highlight_label}, por grupo</h3>
                    <p>Em cada grupo, quantos estão nessa situação. Brasil, ENEM {year}.</p>
                  </div>
                  <label className="filter-field">
                    <span>Separar por</span>
                    <select value={recorte} onChange={(event) => setRecorte(event.target.value)}>
                      {(catalog.data?.recortes || []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                    </select>
                  </label>
                </div>
                {cross.error && <div className="alert" role="alert">{cross.error}</div>}
                {!cross.data ? (!cross.error && <Loading label="Cruzando os dados…" />) : !cross.data.groups.length ? (
                  <p className="pop-note">Não há este cruzamento no ENEM {year}.</p>
                ) : (
                  <Bars categories={cross.data.groups.map((group) => ({ code: group.code, label: group.label, pct: group.highlight_pct }))} />
                )}
              </div>
            </div>
          </>
        )}
      </div>

      <p className="pop-source">
        Fonte: microdados do ENEM (INEP), questionário socioeconômico respondido na inscrição. Percentuais
        entre quem respondeu a cada pergunta. Uma relação entre grupos não indica causa.
      </p>
    </div>
  )
}
