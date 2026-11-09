import { useEffect, useMemo, useState } from 'react'
import Header from './components/layout/Header'
import StatCard from './components/layout/StatCard'
import Loading from './components/common/Loading'
import ErrorState from './components/common/ErrorState'
import PercentileModule from './components/modules/PercentileModule'
import SocioeconomicModule from './components/modules/SocioeconomicModule'
import RegionalModule from './components/modules/RegionalModule'
import EssayModule from './components/modules/EssayModule'
import MyPanorama from './components/panorama/MyPanorama'
import { api } from './services/api'

const navMap = [
  { id: 'overview', label: 'Visão Geral' },
  { id: 'panorama', label: 'Meu Panorama' },
  { id: 'percentile', label: 'Minha Posição' },
  { id: 'socio', label: 'Socioeconômico' },
  { id: 'region', label: 'Estados e Escolas' },
  { id: 'essay', label: 'Redação' },
  { id: 'methodology', label: 'Metodologia' },
]

function App() {
  const [years, setYears] = useState([])
  const [year, setYear] = useState(2024)
  const [summary, setSummary] = useState(null)
  const [source, setSource] = useState('')
  const [active, setActive] = useState('overview')
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    api.years()
      .then((payload) => {
        if (!mounted) return
        const availableYears = payload?.years || []
        setYears(availableYears)
        if (availableYears.length) {
          const latest = Math.max(...availableYears)
          setYear(latest)
        }
        setSource(payload?.data_source || 'demo')
      })
      .catch((err) => {
        if (!mounted) return
        setError(err.message || 'Não foi possível carregar os dados.')
      })

    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!year) return
    setSummary(null)
    api.summary(year)
      .then((payload) => setSummary(payload))
      .catch((err) => setError(err.message || 'Não foi possível carregar o resumo da edição.'))
  }, [year])

  const topStats = useMemo(() => {
    if (!summary) return []
    return [
      { icon: '◎', label: 'Edição', value: String(summary.year), hint: 'análise dentro da mesma edição', accent: 'primary' },
      { icon: '◌', label: 'Participantes', value: Number(summary.participants || 0).toLocaleString('pt-BR'), hint: 'registro válido', accent: 'cyan' },
      { icon: '∑', label: 'Média geral', value: `${Number(summary.means?.MT || 0).toFixed(1)}`, hint: 'matemática', accent: 'violet' },
      { icon: '▣', label: 'Fonte', value: source || 'demo', hint: 'dados ativos', accent: 'success' },
    ]
  }, [summary, source])

  const jumpTo = (sectionId) => {
    setActive(sectionId)
    const target = document.getElementById(sectionId)
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="app-shell">
      <Header source={source || 'demo'} activeSection={active} onNavigate={jumpTo} year={year} years={years} onYearChange={setYear} />

      <main className="page-shell">
        <section id="overview" className="hero-section">
          <div className="hero-copy">
            <span className="section-tag">PANORAMA ENEM</span>
            <h1>Descubra onde seu desempenho se posiciona no ENEM.</h1>
            <p>
              Explore os microdados do INEP e compare seu resultado com milhares de participantes da mesma edição.
            </p>

            <div className="hero-actions">
              <button type="button" className="button button-primary" onClick={() => jumpTo('percentile')}>
                Analisar meu desempenho
              </button>
              <button type="button" className="button button-secondary" onClick={() => jumpTo('methodology')}>
                Conhecer metodologia
              </button>
            </div>

            <div className="hero-meta">
              <div className="meta-pill">
                <span className="dot dot-primary" />
                Fonte ativa: {source || 'demo'}
              </div>
              <div className="meta-pill">
                <span className="dot dot-cyan" />
                {summary ? `${summary.participants.toLocaleString('pt-BR')} participantes` : 'Carregando dados'}
              </div>
            </div>
          </div>

          <div className="hero-panel">
            <div className="panel-header">
              <span className="panel-label">Edição</span>
              <label className="year-picker">
                <select value={year} onChange={(event) => setYear(Number(event.target.value))} aria-label="Selecionar edição do ENEM">
                  {years.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="metric-stack">
              <div className="small-kpi">
                <span className="mini-label">Participantes</span>
                <strong>{summary ? summary.participants.toLocaleString('pt-BR') : '—'}</strong>
              </div>
              <div className="small-kpi accent">
                <span className="mini-label">Média Matemática</span>
                <strong>{summary ? Number(summary.means?.MT || 0).toFixed(1) : '—'}</strong>
              </div>
              <div className="small-kpi">
                <span className="mini-label">Média Redação</span>
                <strong>{summary ? Number(summary.means?.REDACAO || 0).toFixed(1) : '—'}</strong>
              </div>
            </div>
          </div>
        </section>

        {error && (
          <section className="status-block">
            <ErrorState message={error} onRetry={() => api.summary(year).then(setSummary).catch((err) => setError(err.message))} onChangeSource={() => setYear(year)} />
          </section>
        )}

        <section className="stats-grid" aria-label="Resumo da edição">
          {!summary ? <Loading label="Carregando revisão da edição…" /> : topStats.map((item) => (
            <StatCard key={item.label} icon={item.icon} label={item.label} value={item.value} hint={item.hint} accent={item.accent} />
          ))}
        </section>

        <MyPanorama years={years} year={year} source={source} onYearChange={setYear} />

        <div className="module-shell" id="percentile">
          <PercentileModule year={year} />
        </div>

        <div className="module-shell" id="socio">
          <SocioeconomicModule year={year} />
        </div>

        <div className="module-shell" id="region">
          <RegionalModule year={year} />
        </div>

        <div className="module-shell" id="essay">
          <EssayModule year={year} />
        </div>

        <section id="methodology" className="methodology-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">METODOLOGIA</span>
              <h2>Como a análise é construída</h2>
            </div>
            <p>Os dados são tratados com transparência e as comparações são sempre internas à mesma edição.</p>
          </div>

          <div className="methodology-flow" aria-label="Fluxo metodológico">
            {['Microdados INEP', 'ETL', 'Parquet', 'DuckDB', 'FastAPI', 'Panorama ENEM'].map((step, index) => (
              <div key={step} className="flow-step">
                <span>{index + 1}</span>
                <strong>{step}</strong>
              </div>
            ))}
          </div>

          <div className="methodology-cards">
            <article className="method-card">
              <h3>Percentil</h3>
              <p>Mostra a proporção de participantes com nota menor ou igual à informada.</p>
            </article>
            <article className="method-card">
              <h3>Média</h3>
              <p>Indicador central da distribuição da edição analisada.</p>
            </article>
            <article className="method-card">
              <h3>Desvio padrão</h3>
              <p>Expressa a dispersão dos resultados em torno da média.</p>
            </article>
            <article className="method-card">
              <h3>Z-score</h3>
              <p>Indica quantos desvios-padrão a nota está acima ou abaixo da média.</p>
            </article>
          </div>

          <div className="disclaimer-box">
            <strong>Aviso metodológico</strong>
            <p>As análises apresentadas são descritivas e não estabelecem relações causais. A comparação se dá dentro da mesma edição.</p>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <span>Panorama ENEM • dados abertos do INEP</span>
        <span>Gabriel • Guilherme • Pedro • Vítor</span>
      </footer>

      <button type="button" className="back-to-top" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="Voltar ao topo">
        ↑
      </button>
    </div>
  )
}

export default App
