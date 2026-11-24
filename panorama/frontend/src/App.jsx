import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Header from './components/layout/Header'
import ErrorState from './components/common/ErrorState'
import InfoTooltip from './components/common/InfoTooltip'
import AnswerSheet from './components/common/AnswerSheet'
import SocioeconomicModule from './components/modules/SocioeconomicModule'
import RegionalModule from './components/modules/RegionalModule'
import Methodology from './components/modules/Methodology'
import MyPanorama from './components/panorama/MyPanorama'
import PopulationModule from './components/modules/PopulationModule'
import { api } from './services/api'
import { AREAS, DEFAULT_SCORES } from './constants/areas'
import { formatNumber } from './utils/percentile'

export const SECTIONS = [
  { id: 'overview', label: 'Início' },
  { id: 'panorama', label: 'Minhas notas' },
  { id: 'region', label: 'Estados' },
  { id: 'socio', label: 'Renda e família' },
  { id: 'populacao', label: 'Quem faz o ENEM', short: 'Inscritos' },
  { id: 'methodology', label: 'Como funciona' },
]

// Parâmetros do link compartilhável: ?ano=2023&cn=600&ch=...&red=800
const URL_KEYS = { CN: 'cn', CH: 'ch', LC: 'lc', MT: 'mt', REDACAO: 'red' }
const STORAGE_KEY = 'panorama-enem:notas'

function readSaved() {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = Object.fromEntries(AREAS.map(({ code }) => [code, params.get(URL_KEYS[code]) ?? '']))
  if (Object.values(fromUrl).some((value) => value !== '')) {
    return { year: Number(params.get('ano')) || null, scores: { ...DEFAULT_SCORES, ...fromUrl }, fromLink: true }
  }
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
    if (saved?.scores) return { year: saved.year || null, scores: { ...DEFAULT_SCORES, ...saved.scores }, fromLink: false }
  } catch (_) {
    // Navegador sem armazenamento (modo privado, bloqueado): começa com o formulário vazio.
  }
  return { year: Number(params.get('ano')) || null, scores: DEFAULT_SCORES, fromLink: false }
}

export function buildShareUrl(year, scores) {
  const params = new URLSearchParams({ ano: String(year) })
  AREAS.forEach(({ code }) => { if (scores[code] !== '' && scores[code] !== undefined) params.set(URL_KEYS[code], String(scores[code])) })
  return `${window.location.origin}${window.location.pathname}?${params}`
}

const filledScores = (scores) => Object.fromEntries(
  Object.entries(scores).filter(([, value]) => value !== '' && value !== null).map(([key, value]) => [key, Number(value)]),
)

function App() {
  const saved = useRef(readSaved()).current
  const [years, setYears] = useState([])
  const [year, setYear] = useState(saved.year)
  const [summary, setSummary] = useState(null)
  const [source, setSource] = useState('')
  const [active, setActive] = useState('overview')
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [showTop, setShowTop] = useState(false)

  // Notas digitadas, notas do resultado atual e o resultado (sempre da edição `year`).
  const [scores, setScores] = useState(saved.scores)
  const [submitted, setSubmitted] = useState(saved.fromLink ? saved.scores : null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [calcError, setCalcError] = useState('')

  useEffect(() => {
    let mounted = true
    api.years()
      .then((payload) => {
        if (!mounted) return
        const availableYears = payload?.years || []
        setYears(availableYears)
        setYear((current) => (availableYears.includes(current) ? current : Math.max(...availableYears)))
        setSource(payload?.data_source || 'demo')
      })
      .catch((err) => { if (mounted) setError(err.message || 'Não foi possível carregar os dados.') })
    return () => { mounted = false }
  }, [reloadKey])

  useEffect(() => {
    if (!year) return undefined
    let current = true
    setSummary(null)
    api.summary(year)
      .then((payload) => { if (current) setSummary(payload) })
      .catch((err) => { if (current) setError(err.message || 'Não foi possível carregar o resumo da edição.') })
    return () => { current = false }
  }, [year, reloadKey])

  // Calcula (ou recalcula, ao trocar de edição) o resultado das notas enviadas. Assim nunca
  // fica na tela um resultado de outra edição.
  useEffect(() => {
    if (!year || !years.length || !submitted) return undefined
    const payload = filledScores(submitted)
    if (!Object.keys(payload).length) return undefined
    let current = true
    setBusy(true)
    setCalcError('')
    api.percentile(year, payload)
      .then((response) => { if (current) setResult({ ...response, year }) })
      .catch((err) => {
        if (!current) return
        setResult(null)
        setCalcError(err.message)
      })
      .finally(() => { if (current) setBusy(false) })
    return () => { current = false }
  }, [year, years.length, submitted])

  // Mantém o link e o navegador lembrando a edição e as notas do último resultado.
  useEffect(() => {
    if (!year) return
    const url = submitted ? buildShareUrl(year, submitted) : `${window.location.pathname}?ano=${year}`
    window.history.replaceState(null, '', url)
    if (submitted) {
      try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ year, scores: submitted })) } catch (_) { /* sem armazenamento */ }
    }
  }, [year, submitted])

  const submitScores = useCallback(() => {
    setSubmitted({ ...scores })
    requestAnimationFrame(() => document.getElementById('panorama-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }, [scores])

  // Destaca no menu a seção que está no meio da tela.
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) setActive(entry.target.id) })
    }, { rootMargin: '-45% 0px -50% 0px' })
    SECTIONS.forEach(({ id }) => {
      const element = document.getElementById(id)
      if (element) observer.observe(element)
    })
    const onScroll = () => setShowTop(window.scrollY > 900)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      observer.disconnect()
      window.removeEventListener('scroll', onScroll)
    }
  }, [])

  const retry = () => {
    setError('')
    setReloadKey((key) => key + 1)
  }

  const focusYearPicker = () => {
    const picker = document.querySelector('.header-year select')
    picker?.focus()
  }

  const jumpTo = (sectionId) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const startWithScores = () => {
    jumpTo('panorama')
    window.setTimeout(() => document.querySelector('.panorama-score-grid input')?.focus({ preventScroll: true }), 500)
  }

  // Média geral: média das cinco áreas (quatro provas objetivas e redação) da edição.
  const overallMean = useMemo(() => {
    const values = Object.values(summary?.means || {}).map(Number).filter((value) => !Number.isNaN(value))
    return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null
  }, [summary])

  const sourceLabel = source === 'official' ? 'Dados oficiais do INEP' : source === 'demo' ? 'Dados de demonstração' : error ? 'Dados indisponíveis' : 'Carregando dados…'
  const skeleton = (width) => <span className="kpi-skeleton shimmer" style={width ? { width } : undefined} aria-label="Carregando" />

  return (
    <div className="app-shell">
      <Header sections={SECTIONS} activeSection={active} onNavigate={jumpTo} year={year} years={years} onYearChange={setYear} />

      <main className="page-shell" id="conteudo" tabIndex={-1}>
        <section id="overview" className="hero-section">
          <AnswerSheet />
          <div className="hero-copy">
            <h1>Descubra onde sua nota te coloca no ENEM.</h1>
            <p>
              Digite suas notas e compare com todos os participantes da mesma edição, usando os microdados oficiais do INEP.
            </p>

            <div className="hero-actions">
              <button type="button" className="button button-primary" onClick={startWithScores}>
                Comparar minhas notas
              </button>
              <button type="button" className="button button-secondary" onClick={() => jumpTo('methodology')}>
                Como funciona
              </button>
            </div>

            <p className="hero-source"><span className={source === 'demo' ? 'dot dot-warning' : 'dot dot-primary'} />{sourceLabel}</p>
          </div>

          <div className="hero-panel">
            <h2 className="hero-panel-title">ENEM {year || '…'} em números</h2>
            <div className="metric-stack">
              <div className="small-kpi">
                <span className="mini-label">
                  Participantes
                  <InfoTooltip label="Participantes" align="right" text="Pessoas desta edição usadas nos cálculos. Ficam de fora os registros com nota zero em alguma prova objetiva, como recomenda o INEP, porque distorcem médias e comparações." />
                </span>
                <strong>{summary ? summary.participants.toLocaleString('pt-BR') : skeleton(150)}</strong>
              </div>
              <div className="small-kpi accent">
                <span className="mini-label">
                  Média geral
                  <InfoTooltip label="Média geral" align="right" text="Média das cinco áreas nesta edição: Ciências da Natureza, Ciências Humanas, Linguagens, Matemática e Redação." />
                </span>
                <strong>{summary ? formatNumber(overallMean, 1) : skeleton()}</strong>
              </div>
              <div className="small-kpi">
                <span className="mini-label">
                  Redações nota 1000
                  <InfoTooltip label="Redações nota 1000" align="right" text="Quantas redações receberam a nota máxima nesta edição, entre os participantes usados nos cálculos." />
                </span>
                <strong>{summary ? (summary.essay_perfect ?? '—').toLocaleString('pt-BR') : skeleton()}</strong>
              </div>
            </div>
          </div>
        </section>

        {error && (
          <section className="status-block">
            <ErrorState message={error} onRetry={retry} onChangeSource={years.length ? focusYearPicker : undefined} />
          </section>
        )}

        <MyPanorama
          year={year}
          source={source}
          scores={scores}
          onScoresChange={setScores}
          onSubmit={submitScores}
          result={result}
          busy={busy}
          error={calcError}
        />

        <section className="module-shell" id="region">
          <RegionalModule year={year} years={years} onYearChange={setYear} userResult={result} />
        </section>

        <section className="module-shell" id="socio">
          <SocioeconomicModule year={year} means={summary?.means} years={years} onYearChange={setYear} scores={scores} />
        </section>

        <section className="module-shell" id="populacao">
          <PopulationModule year={year} years={years} onYearChange={setYear} />
        </section>

        <Methodology />
      </main>

      <footer className="site-footer">
        <span>Panorama ENEM, feito com os dados abertos do INEP</span>
        <span>Gabriel, Guilherme, Pedro e Vítor</span>
      </footer>

      <button type="button" className={showTop ? 'back-to-top visible' : 'back-to-top'} onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="Voltar ao topo" tabIndex={showTop ? 0 : -1}>
        ↑
      </button>
    </div>
  )
}

export default App
