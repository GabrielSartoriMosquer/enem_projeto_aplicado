import { useEffect, useMemo, useState } from 'react'
import Loading from '../common/Loading'
import { api } from '../../services/api'

const AREAS = [
  ['CN', 'Ciências da Natureza'],
  ['CH', 'Ciências Humanas'],
  ['LC', 'Linguagens e Códigos'],
  ['MT', 'Matemática'],
  ['REDACAO', 'Redação'],
]

export default function SocioeconomicModule({ year }) {
  const [area, setArea] = useState('MT')
  const [dimension, setDimension] = useState('renda')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setData(null)
    setError('')
    api.socioeconomic(year, area, dimension)
      .then((payload) => {
        if (active) setData(payload)
      })
      .catch((err) => {
        if (active) setError(err.message)
      })
    return () => { active = false }
  }, [year, area, dimension])

  const summary = useMemo(() => {
    // Os grupos chegam ordenados pelo código do INEP (A, B, C…), não pela média. Na escolaridade
    // o último é "Não sabe", então maior e menor média precisam ser buscadas.
    const groups = (data?.groups || []).filter((group) => Number.isFinite(group.mean))
    if (!groups.length) return null
    const highest = groups.reduce((best, group) => (group.mean > best.mean ? group : best))
    const lowest = groups.reduce((worst, group) => (group.mean < worst.mean ? group : worst))
    return {
      first: lowest,
      last: highest,
      delta: highest.mean - lowest.mean,
    }
  }, [data])

  return (
    <div className="module-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">MÓDULO 2</span>
          <h2>Equidade socioeconômica</h2>
        </div>
        <p>Compare médias por renda e escolaridade familiar sem inferir causalidade.</p>
      </div>

      <div className="filter-row">
        <label className="filter-field">
          <span>Área</span>
          <select value={area} onChange={(event) => setArea(event.target.value)}>
            {AREAS.map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
        </label>

        <label className="filter-field">
          <span>Recorte</span>
          <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
            <option value="renda">Renda familiar (Q006)</option>
            <option value="escolaridade_mae">Escolaridade da mãe (Q002)</option>
            <option value="escolaridade_pai">Escolaridade do pai (Q001)</option>
          </select>
        </label>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}

      {!data ? (
        !error && <Loading label="Carregando panorama socioeconômico…" />
      ) : !data.groups?.length ? (
        <div className="insight-banner subtle" role="status">
          <strong>Sem dados para este recorte em {year}.</strong>
          <span>Nesta edição o INEP publicou o questionário socioeconômico separado das notas, sem como ligar os dois. O recorte está disponível de 2018 a 2023.</span>
        </div>
      ) : (
        <>
          {summary && (
            <div className="insight-banner subtle">
              <strong>Comparação por grupo:</strong>
              <span>o grupo de maior média ficou {summary.last.category} com média {Number(summary.last.mean).toFixed(1)} e diferença de {Number(summary.delta).toFixed(1)} pontos em relação ao grupo de menor média ({summary.first.category}).</span>
            </div>
          )}

          <div className="chart-grid two-col">
            <div className="chart-card">
              <h3>Ranking por grupo</h3>
              <div className="bar-chart" role="img" aria-label="Ranking socioeconômico">
                {(data.groups || []).map((group) => {
                  const width = Math.max(12, (group.mean / 1000) * 100)
                  return (
                    <div className="bar-row" key={group.code || group.category}>
                      <div className="bar-meta">
                        <span>{group.category}</span>
                        <strong>{Number(group.mean).toFixed(1)}</strong>
                      </div>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${width}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="chart-card">
              <h3>Resumo do grupo</h3>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Grupo</th>
                      <th>n</th>
                      <th>Média</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.groups || []).map((group) => (
                      <tr key={group.code || group.category}>
                        <td>{group.category}</td>
                        <td>{group.n}</td>
                        <td>{Number(group.mean).toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
