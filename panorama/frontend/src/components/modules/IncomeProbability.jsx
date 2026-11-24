import { useEffect, useRef, useState } from 'react'
import Loading from '../common/Loading'
import { api } from '../../services/api'
import { AREAS } from '../../constants/areas'
import { INCOME_BANDS } from '../../constants/income'
import { formatInteger, formatNumber } from '../../utils/percentile'

// Uma proporção pequena não vira "0,0%", que seria lido como "ninguém".
const pct = (value) => {
  if (value === null || value === undefined) return '—'
  if (value > 0 && value < 0.001) return 'menos de 0,1%'
  return `${formatNumber(value * 100, 1)}%`
}
const prob = (value) => {
  if (value === null || value === undefined) return '—'
  return value > 0 && value < 0.0001 ? '< 0,0001' : formatNumber(value, 4)
}
const percentile = (value) => (value === null || value === undefined ? '—' : formatNumber(value, 1))

// Probabilidade condicional entre nota e renda. O cálculo é da API (income_model.py); aqui só
// aparecem as duas respostas e a conta, para quem quiser conferir.
export default function IncomeProbability({ year, scores = {} }) {
  const [area, setArea] = useState('MT')
  const [score, setScore] = useState(scores.MT ?? '')
  const [income, setIncome] = useState('')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lastRequest = useRef(0)

  // Trocar a edição ou qualquer campo descarta o resultado anterior, inclusive uma resposta
  // que ainda esteja a caminho: a tela nunca mostra a conta de outra entrada.
  useEffect(() => {
    lastRequest.current += 1
    setData(null)
    setError('')
    setBusy(false)
  }, [year, area, score, income])

  const changeArea = (code) => {
    setArea(code)
    if (scores[code] !== undefined && scores[code] !== '') setScore(scores[code])
  }

  const submit = (event) => {
    event.preventDefault()
    const id = lastRequest.current + 1
    lastRequest.current = id
    setBusy(true)
    setError('')
    api.incomeProbability(year, area, score, income)
      .then((payload) => { if (id === lastRequest.current) setData(payload) })
      .catch((err) => { if (id === lastRequest.current) setError(err.message) })
      .finally(() => { if (id === lastRequest.current) setBusy(false) })
  }

  const mine = data?.bands.find((band) => band.code === data.income)
  const scoreText = data ? formatNumber(data.score, Number.isInteger(data.score) ? 0 : 1) : ''

  return (
    <div className="income-model">
      <h3>Sua nota entre pessoas com a mesma renda</h3>
      <p className="income-intro">
        Informe uma nota e a renda da família para comparar sua posição em grupos diferentes do ENEM {year}.
        Nada do que você digita fica guardado.
      </p>

      <form className="filter-row" onSubmit={submit}>
        <label className="filter-field">
          <span>Área da nota</span>
          <select value={area} onChange={(event) => changeArea(event.target.value)}>
            {AREAS.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="score-field">
          <span>Sua nota</span>
          <input type="number" inputMode="decimal" min="0" max="1000" step="0.1" required value={score} onChange={(event) => setScore(event.target.value)} />
        </label>
        <label className="filter-field">
          <span>Renda mensal da família</span>
          <select required value={income} onChange={(event) => setIncome(event.target.value)}>
            <option value="">Escolha a faixa</option>
            {INCOME_BANDS.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <button type="submit" className="button button-primary income-submit" disabled={busy}>Comparar</button>
      </form>

      {error && <div className="alert" role="alert">{error}</div>}
      {busy && <Loading label="Calculando as probabilidades…" />}

      {data && mine && (
        <div aria-live="polite">
          <div className="income-cards">
            <div className="income-card">
              <span>Entre todos</span>
              <strong>{percentile(data.percentile)}</strong>
              <small>percentil, {formatInteger(data.n)} pessoas</small>
            </div>
            <div className="income-card accent">
              <span>{mine.label}</span>
              <strong>{percentile(mine.percentile)}</strong>
              <small>percentil, {formatInteger(mine.n)} pessoas</small>
            </div>
            <div className="income-card">
              <span>{data.reference.label}</span>
              <strong>{percentile(data.reference.percentile)}</strong>
              <small>percentil, {formatInteger(data.reference.n)} pessoas que informaram a escola</small>
            </div>
          </div>

          <ul className="income-answers">
            <li>
              Entre quem tem renda na sua faixa, <strong>{pct(mine.likelihood)}</strong> tirou {scoreText} ou mais em {data.area_label}.
              Entre todos, foram {pct(data.total_probability)}.
            </li>
            {data.bayes_available ? (
              <li>
                Entre quem tirou {scoreText} ou mais, <strong>{pct(mine.posterior)}</strong> tem renda na sua faixa,
                que reúne {pct(mine.prior)} dos participantes.
              </li>
            ) : (
              <li>Pouca gente alcançou essa nota nesta edição, então não mostramos a divisão por renda.</li>
            )}
          </ul>

          <details className="income-details">
            <summary>Ver a conta</summary>
            <div className="income-table">
              <table>
                <caption>X é a nota em {data.area_label}; r é a faixa de renda. ENEM {data.year}.</caption>
                <thead>
                  <tr>
                    <th scope="col">Renda (r)</th>
                    <th scope="col">Pessoas</th>
                    <th scope="col">P(r)</th>
                    <th scope="col">P(X ≥ {scoreText} | r)</th>
                    <th scope="col">Produto</th>
                    <th scope="col">P(r | X ≥ {scoreText})</th>
                  </tr>
                </thead>
                <tbody>
                  {data.bands.map((band) => (
                    <tr key={band.code} className={band.code === data.income ? 'current' : undefined}>
                      <th scope="row">{band.label}</th>
                      <td>{formatInteger(band.n)}</td>
                      <td>{prob(band.prior)}</td>
                      <td>{prob(band.likelihood)}</td>
                      <td>{prob(band.joint)}</td>
                      <td>{prob(band.posterior)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">Total</th>
                    <td>{formatInteger(data.n)}</td>
                    <td>{prob(1)}</td>
                    <td />
                    <td>{prob(data.total_probability)}</td>
                    <td>{data.bayes_available ? prob(1) : '—'}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <p>
              O produto é P(r) × P(X ≥ {scoreText} | r). A soma dos produtos é a probabilidade total, e cada produto dividido por ela dá a última coluna (Teorema de Bayes).
            </p>
          </details>

          <p className="income-note">
            Isso descreve grupos desta edição. Não prevê sua nota e não quer dizer que a renda é a causa da diferença.
            Só entra quem fez a prova, e quem tem renda menor falta mais.
          </p>
        </div>
      )}
    </div>
  )
}
