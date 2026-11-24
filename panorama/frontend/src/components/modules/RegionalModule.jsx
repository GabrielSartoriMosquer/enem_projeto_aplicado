import { useEffect, useMemo, useState } from 'react'
import Loading from '../common/Loading'
import BrazilMap from '../brazil-map/BrazilMap'
import { api } from '../../services/api'
import { formatNumber, formatSigned as signed } from '../../utils/percentile'
import { FIRST_LINKED_YEAR as FIRST_MAP_YEAR, LAST_LINKED_YEAR as LAST_MAP_YEAR, isLinkedYear } from '../../constants/areas'

const AREAS = [
  ['CN', 'Ciências da Natureza'],
  ['CH', 'Ciências Humanas'],
  ['LC', 'Linguagens e Códigos'],
  ['MT', 'Matemática'],
  ['REDACAO', 'Redação'],
]

const SORTS = [
  ['mean-desc', 'Maior média primeiro'],
  ['mean-asc', 'Menor média primeiro'],
  ['name', 'Ordem alfabética'],
  ['n-desc', 'Mais participantes primeiro'],
]

export default function RegionalModule({ year, years = [], onYearChange, userResult }) {
  const [area, setArea] = useState('MT')
  const [schoolType, setSchoolType] = useState('')
  const [data, setData] = useState(null)
  const [selectedUf, setSelectedUf] = useState('')
  const [sort, setSort] = useState('mean-desc')
  const [error, setError] = useState('')
  const [schoolTypes, setSchoolTypes] = useState(null)

  const available = isLinkedYear(year)
  const fallbackYear = [...years].filter(isLinkedYear).sort((a, b) => b - a)[0]

  useEffect(() => {
    if (!available) return undefined
    let active = true
    api.options(year)
      .then((payload) => {
        if (!active) return
        const list = payload?.school_types || []
        setSchoolTypes(list)
        setSchoolType((current) => (list.some((item) => String(item.code) === current) ? current : ''))
      })
      .catch(() => { if (active) setSchoolTypes(null) })
    return () => { active = false }
  }, [year, available])

  useEffect(() => {
    if (!available) {
      setData(null)
      return undefined
    }
    let active = true
    setData(null)
    setError('')
    api.regionSchool(year, area, schoolType)
      .then((payload) => {
        if (!active) return
        setData(payload)
        setSelectedUf((current) => current || payload.states.find((item) => item.mean !== null)?.uf || payload.states[0]?.uf || '')
      })
      .catch((err) => {
        if (active) setError(err.message)
      })
    return () => { active = false }
  }, [year, area, schoolType, available])

  const ranked = useMemo(
    () => (data?.states || []).filter((state) => state.mean !== null).sort((left, right) => right.mean - left.mean),
    [data],
  )
  const positionOf = useMemo(() => Object.fromEntries(ranked.map((state, index) => [state.uf, index + 1])), [ranked])
  const alphabetical = useMemo(
    () => [...(data?.states || [])].sort((left, right) => left.name.localeCompare(right.name, 'pt-BR')),
    [data],
  )

  const rows = useMemo(() => {
    if (!data?.states) return []
    return [...data.states].sort((left, right) => {
      if (sort === 'name') return left.name.localeCompare(right.name, 'pt-BR')
      if (sort === 'mean-asc') return (left.mean ?? Number.POSITIVE_INFINITY) - (right.mean ?? Number.POSITIVE_INFINITY)
      if (sort === 'n-desc') return right.n - left.n
      return (right.mean ?? Number.NEGATIVE_INFINITY) - (left.mean ?? Number.NEGATIVE_INFINITY)
    })
  }, [data, sort])

  // Escala do ranking: a maior distância (para cima ou para baixo) até a média nacional ocupa
  // metade da barra; o centro da barra é a média do Brasil.
  const national = data?.national_mean ?? null
  const spread = national === null ? 0 : Math.max(1, ...ranked.map((state) => Math.abs(state.mean - national)))

  const selected = data?.states.find((state) => state.uf === selectedUf)
  const selectedPosition = selected ? positionOf[selected.uf] : null
  const areaLabel = data?.area_label || AREAS.find(([id]) => id === area)?.[1]

  // Ponte com o resultado da pessoa: a nota dela na área escolhida, comparada às médias estaduais.
  const userScore = userResult?.year === year ? userResult.results.find((item) => item.area === area)?.score ?? null : null
  const statesBelowUser = userScore === null ? 0 : ranked.filter((state) => state.mean < userScore).length

  return (
    <div className="module-panel regional-module">
      <div className="section-heading">
        <h2>Como cada estado se saiu</h2>
        <p>Compare a média de cada estado com a média do Brasil, por área e tipo de escola.</p>
      </div>

      {!available ? (
        <div className="map-unavailable" role="status">
          <h3>O mapa por estado não está disponível no ENEM {year}</h3>
          <p>
            A partir de 2024, o INEP passou a publicar os microdados anonimizados, seguindo a LGPD
            (Lei Geral de Proteção de Dados). Com isso, a nota de cada participante não pode mais ser
            ligada ao estado onde fez a prova. O mapa funciona para as edições de {FIRST_MAP_YEAR} a {LAST_MAP_YEAR}.
          </p>
          {fallbackYear && onYearChange && (
            <button type="button" className="button button-primary" onClick={() => onYearChange(fallbackYear)}>
              Ver o mapa do ENEM {fallbackYear}
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="regional-toolbar">
            <label className="filter-field"><span>Área</span><select value={area} onChange={(event) => setArea(event.target.value)}>{AREAS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
            <label className="filter-field">
              <span>Tipo de escola</span>
              <select value={schoolType} onChange={(event) => setSchoolType(event.target.value)}>
                <option value="">Todos os tipos</option>
                {(schoolTypes?.length ? schoolTypes : [{ code: 2, label: 'Pública' }, { code: 3, label: 'Privada' }, { code: 1, label: 'Não respondeu' }])
                  .map((item) => <option key={item.code} value={String(item.code)}>{item.label}</option>)}
              </select>
            </label>
            <label className="filter-field">
              <span>Estado</span>
              <select value={selectedUf} onChange={(event) => setSelectedUf(event.target.value)} disabled={!data}>
                {!alphabetical.length && <option value="">Carregando…</option>}
                {alphabetical.map((state) => <option key={state.uf} value={state.uf}>{state.name}</option>)}
              </select>
            </label>
          </div>

          {userScore !== null && data && (
            <p className="user-bridge">
              Sua nota de {areaLabel} ({formatNumber(userScore, 1)}) fica acima da média de <strong>{statesBelowUser} dos {ranked.length} estados</strong>.
            </p>
          )}

          {error && <div className="alert" role="alert">{error}</div>}
          {!data ? (!error && <Loading label="Buscando dados dos 27 estados…" />) : (
            <>
              <div className="regional-overview">
                <div className="regional-map-card">
                  <div className="chart-card-heading">
                    <h3>Média de {areaLabel} no ENEM {year}</h3>
                    <span className="coverage-badge">{data.states_with_data} de 27 estados com dados</span>
                  </div>
                  <p className="map-hint">Clique em um estado para ver os detalhes.</p>
                  <BrazilMap states={data.states} selectedUf={selectedUf} onSelect={setSelectedUf} areaLabel={areaLabel} />
                </div>

                <div className="selected-state-card" aria-live="polite">
                  {selected ? <>
                    <h3>{selected.name}</h3>
                    <p className="selected-context">{areaLabel} no ENEM {year}</p>
                    <div className="selected-metrics">
                      <div><span>Média do estado</span><strong>{formatNumber(selected.mean, 1)}</strong></div>
                      <div><span>Diferença para o Brasil</span><strong>{selected.mean !== null && national !== null ? signed(selected.mean - national) : 'Indisponível'}</strong></div>
                      <div><span>Posição entre os estados</span><strong>{selectedPosition ? `${selectedPosition}º de ${ranked.length}` : 'Indisponível'}</strong></div>
                      <div><span>Participantes</span><strong>{selected.n.toLocaleString('pt-BR')}</strong></div>
                      {userScore !== null && selected.mean !== null && (
                        <div className="selected-user"><span>Sua nota comparada ao estado</span><strong>{signed(userScore - selected.mean)}</strong></div>
                      )}
                    </div>
                    {selected.mean === null && <div className="no-data-message">Este estado não tem dados nesta edição.</div>}
                  </> : <p className="selected-context">Clique em um estado no mapa ou escolha um na lista.</p>}
                </div>
              </div>

              <div className="ranking-card">
                <div className="ranking-heading">
                  <div>
                    <h3>Ranking dos estados</h3>
                    <p>
                      A linha do meio é a média do Brasil{national !== null ? ` (${formatNumber(national, 1)})` : ''}.
                      Barras à direita ficam acima dela; à esquerda, abaixo.
                    </p>
                  </div>
                  <label className="filter-field ranking-sort">
                    <span>Ordenar</span>
                    <select value={sort} onChange={(event) => setSort(event.target.value)}>{SORTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>
                  </label>
                </div>

                <ol className="state-ranking-list" style={{ '--rows': Math.ceil(rows.length / 2) }}>
                  {rows.map((state) => {
                    const diff = state.mean === null || national === null ? null : state.mean - national
                    const width = diff === null ? 0 : (Math.abs(diff) / spread) * 50
                    return (
                      <li key={state.uf}>
                        <button
                          type="button"
                          className={selectedUf === state.uf ? 'state-ranking-row selected' : 'state-ranking-row'}
                          aria-pressed={selectedUf === state.uf}
                          onClick={() => setSelectedUf(state.uf)}
                        >
                          <span className="state-rank-position">{positionOf[state.uf] ? `${positionOf[state.uf]}º` : '—'}</span>
                          <span className="state-rank-name">{state.name}</span>
                          <span className="state-rank-bar" aria-hidden="true">
                            {diff !== null && (
                              <i
                                className={diff >= 0 ? 'above' : 'below'}
                                style={diff >= 0 ? { left: '50%', width: `${width}%` } : { right: '50%', width: `${width}%` }}
                              />
                            )}
                          </span>
                          <span className="state-rank-value">
                            {state.mean === null ? 'Sem dados' : formatNumber(state.mean, 1)}
                            {diff !== null && <small className={diff >= 0 ? 'above' : 'below'}>{signed(diff)}</small>}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ol>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
