import { useEffect, useMemo, useState } from 'react'
import Loading from '../common/Loading'
import BrazilMap from '../brazil-map/BrazilMap'
import { api } from '../../services/api'
import { formatNumber } from '../../utils/percentile'

const AREAS = [
  ['CN', 'Ciências da Natureza'],
  ['CH', 'Ciências Humanas'],
  ['LC', 'Linguagens e Códigos'],
  ['MT', 'Matemática'],
  ['REDACAO', 'Redação'],
]

const SORTS = [
  ['name', 'Alfabética'],
  ['mean-desc', 'Maior média'],
  ['mean-asc', 'Menor média'],
  ['n-desc', 'Maior população'],
]

export default function RegionalModule({ year }) {
  const [area, setArea] = useState('MT')
  const [schoolType, setSchoolType] = useState('')
  const [data, setData] = useState(null)
  const [selectedUf, setSelectedUf] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('mean-desc')
  const [error, setError] = useState('')

  useEffect(() => {
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
  }, [year, area, schoolType])

  const states = useMemo(() => {
    if (!data?.states) return []
    const normalized = query.trim().toLocaleLowerCase('pt-BR')
    const filtered = data.states.filter((state) => !normalized || state.uf.toLocaleLowerCase().includes(normalized) || state.name.toLocaleLowerCase().includes(normalized))
    return [...filtered].sort((left, right) => {
      if (sort === 'name') return left.name.localeCompare(right.name, 'pt-BR')
      if (sort === 'mean-asc') return (left.mean ?? Number.POSITIVE_INFINITY) - (right.mean ?? Number.POSITIVE_INFINITY)
      if (sort === 'n-desc') return right.n - left.n
      return (right.mean ?? Number.NEGATIVE_INFINITY) - (left.mean ?? Number.NEGATIVE_INFINITY)
    })
  }, [data, query, sort])

  const selected = data?.states.find((state) => state.uf === selectedUf)
  const ranked = data?.states.filter((state) => state.mean !== null).sort((left, right) => right.mean - left.mean) || []
  const selectedPosition = selected?.mean === null ? null : ranked.findIndex((state) => state.uf === selected?.uf) + 1

  return (
    <div className="module-panel regional-module">
      <div className="section-heading">
        <div>
          <span className="eyebrow">MÓDULO 3</span>
          <h2>Estados e tipo de escola</h2>
        </div>
        <p>Explore as 27 UFs e compare apenas os dados efetivamente disponíveis para a edição selecionada.</p>
      </div>

      <div className="regional-toolbar">
        <label className="filter-field"><span>Área</span><select value={area} onChange={(event) => setArea(event.target.value)}>{AREAS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label className="filter-field"><span>Tipo de escola</span><select value={schoolType} onChange={(event) => setSchoolType(event.target.value)}><option value="">Todos os tipos</option><option value="2">Pública</option><option value="3">Privada</option><option value="1">Não respondeu</option></select></label>
        <label className="filter-field search-field"><span>Pesquisar UF</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome ou sigla" /></label>
        <label className="filter-field"><span>Ordenar</span><select value={sort} onChange={(event) => setSort(event.target.value)}>{SORTS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}
      {!data ? (!error && <Loading label="Buscando dados das 27 UFs…" />) : (
        <>
          <div className="regional-overview">
            <div className="regional-map-card">
              <div className="chart-card-heading"><div><span className="mini-label">MAPA DO BRASIL</span><h3>{data.area_label} • ENEM {year}</h3></div><span className="coverage-badge">{data.states_with_data} / 27 com dados</span></div>
              <BrazilMap states={data.states} selectedUf={selectedUf} onSelect={setSelectedUf} areaLabel={data.area_label} year={year} />
            </div>
            <div className="selected-state-card">
              <span className="mini-label">UF SELECIONADA</span>
              {selected ? <>
                <h3>{selected.name} <small>{selected.uf}</small></h3>
                <p className="selected-context">ENEM {year} • {data.area_label}</p>
                <div className="selected-metrics">
                  <div><span>Média estadual</span><strong>{formatNumber(selected.mean, 2)}</strong></div>
                  <div><span>Participantes</span><strong>{selected.n.toLocaleString('pt-BR')}</strong></div>
                  <div><span>Posição entre UFs</span><strong>{selectedPosition ? `${selectedPosition}º de ${ranked.length}` : 'Indisponível'}</strong></div>
                  <div><span>Diferença para Brasil</span><strong>{selected.mean !== null && data.national_mean !== null ? `${selected.mean - data.national_mean >= 0 ? '+' : ''}${formatNumber(selected.mean - data.national_mean, 2)}` : 'Indisponível'}</strong></div>
                </div>
                {selected.mean === null && <div className="no-data-message">Sem dados nesta edição</div>}
              </> : <p>Selecione uma UF no mapa ou na lista.</p>}
            </div>
          </div>

          <div className="ranking-card">
            <div className="chart-card-heading"><div><span className="mini-label">RANKING COMPLETO</span><h3>Comparação entre UFs</h3></div><span className="ranking-count">{states.length} estados exibidos</span></div>
            <div className="state-ranking-list">
              {states.map((state) => <button type="button" className={selectedUf === state.uf ? 'state-ranking-row selected' : 'state-ranking-row'} key={state.uf} onClick={() => setSelectedUf(state.uf)}>
                <strong>{state.mean === null ? '—' : String(state.position || ranked.findIndex((item) => item.uf === state.uf) + 1).padStart(2, '0')}</strong><span className="state-rank-name"><b>{state.uf}</b>{state.name}</span><span className="state-rank-bar"><i style={{ width: `${state.mean === null || !data.national_mean ? 0 : Math.max(4, (state.mean / 1000) * 100)}%` }} /></span><span className="state-rank-value">{state.mean === null ? 'Sem dados' : formatNumber(state.mean, 1)}</span></button>)}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
