import { useEffect, useMemo, useState } from 'react'
import IncomeProbability from './IncomeProbability'
import Loading from '../common/Loading'
import { api } from '../../services/api'
import { AREAS, FIRST_LINKED_YEAR, LAST_LINKED_YEAR, isLinkedYear } from '../../constants/areas'
import { formatInteger, formatNumber, formatSigned } from '../../utils/percentile'

const DIMENSIONS = [
  ['renda', 'Renda da família'],
  ['escolaridade_mae', 'Escolaridade da mãe'],
  ['escolaridade_pai', 'Escolaridade do pai'],
]

export default function SocioeconomicModule({ year, means, years = [], onYearChange, scores }) {
  const [area, setArea] = useState('MT')
  const [dimension, setDimension] = useState('renda')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const available = isLinkedYear(year)
  const fallbackYear = [...years].filter(isLinkedYear).sort((a, b) => b - a)[0]

  useEffect(() => {
    if (!year || !available) return undefined
    let active = true
    setData(null)
    setError('')
    api.socioeconomic(year, area, dimension)
      .then((payload) => { if (active) setData(payload) })
      .catch((err) => { if (active) setError(err.message) })
    return () => { active = false }
  }, [year, area, dimension, available])

  const groups = useMemo(() => (data?.groups || []).filter((group) => Number.isFinite(group.mean)), [data])
  const areaLabel = AREAS.find((item) => item.code === area)?.label
  const reference = Number.isFinite(means?.[area]) ? means[area] : null

  const summary = useMemo(() => {
    // Os grupos chegam na ordem do questionário (da menor renda para a maior), não pela média.
    if (!groups.length) return null
    const highest = groups.reduce((best, group) => (group.mean > best.mean ? group : best))
    const lowest = groups.reduce((worst, group) => (group.mean < worst.mean ? group : worst))
    return { highest, lowest, delta: highest.mean - lowest.mean }
  }, [groups])

  const spread = reference === null ? 1 : Math.max(1, ...groups.map((group) => Math.abs(group.mean - reference)))

  return (
    <div className="module-panel">
      <div className="section-heading">
        <h2>Renda, família e nota</h2>
        <p>Veja como a média muda conforme a renda e a escolaridade da família.</p>
      </div>

      {!available ? (
        <div className="map-unavailable" role="status">
          <h3>Este recorte não está disponível no ENEM {year}</h3>
          <p>
            A partir de 2024, o INEP publica o questionário socioeconômico separado das notas, para proteger
            os participantes (LGPD). Por isso não há como ligar renda e escolaridade à nota. O recorte funciona
            para as edições de {FIRST_LINKED_YEAR} a {LAST_LINKED_YEAR}.
          </p>
          {fallbackYear && onYearChange && (
            <button type="button" className="button button-primary" onClick={() => onYearChange(fallbackYear)}>
              Ver o ENEM {fallbackYear}
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="filter-row">
            <label className="filter-field">
              <span>Área</span>
              <select value={area} onChange={(event) => setArea(event.target.value)}>
                {AREAS.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}
              </select>
            </label>
            <label className="filter-field">
              <span>Comparar por</span>
              <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
                {DIMENSIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
          </div>

          {error && <div className="alert" role="alert">{error}</div>}
          {!data ? (!error && <Loading label="Buscando as médias por grupo…" />) : !groups.length ? (
            <div className="map-unavailable" role="status"><p>Não há dados para este recorte no ENEM {year}.</p></div>
          ) : (
            <>
              {summary && (
                <p className="socio-summary">
                  Em {areaLabel}, o grupo <strong>“{summary.highest.category}”</strong> teve média {formatNumber(summary.highest.mean, 1)},{' '}
                  <strong>{formatNumber(summary.delta, 1)} pontos</strong> acima do grupo “{summary.lowest.category}” ({formatNumber(summary.lowest.mean, 1)}).
                  {' '}Isso mostra uma relação nos dados, não uma causa.
                </p>
              )}

              <div className="ranking-card socio-chart">
                <div className="ranking-heading">
                  <div>
                    <h3>Média de {areaLabel} por grupo</h3>
                    {reference !== null && (
                      <p>A linha do meio é a média de todos os participantes ({formatNumber(reference, 1)}). Barras à direita ficam acima dela; à esquerda, abaixo.</p>
                    )}
                  </div>
                </div>
                <ol className="socio-list">
                  {groups.map((group) => {
                    const diff = reference === null ? null : group.mean - reference
                    const width = diff === null ? 0 : (Math.abs(diff) / spread) * 50
                    return (
                      <li key={group.code || group.category} className="socio-row">
                        <span className="socio-label">
                          {group.category}
                          <small>{formatInteger(group.n)} participantes</small>
                        </span>
                        <span className="state-rank-bar" aria-hidden="true">
                          {diff !== null && (
                            <i className={diff >= 0 ? 'above' : 'below'} style={diff >= 0 ? { left: '50%', width: `${width}%` } : { right: '50%', width: `${width}%` }} />
                          )}
                        </span>
                        <span className="state-rank-value">
                          {formatNumber(group.mean, 1)}
                          {diff !== null && <small className={diff >= 0 ? 'above' : 'below'}>{formatSigned(diff)}</small>}
                        </span>
                      </li>
                    )
                  })}
                </ol>
              </div>
            </>
          )}

          <IncomeProbability year={year} scores={scores} />
        </>
      )}
    </div>
  )
}
