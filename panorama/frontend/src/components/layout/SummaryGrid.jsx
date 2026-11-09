import { Loading } from '../Loading'
import { StatCard } from './StatCard'

export function SummaryGrid({ summary, year }) {
  if (!summary) return <Loading />

  return (
    <section className="summary-grid" aria-label="Resumo da edição">
      <StatCard label="Participantes no conjunto" value={summary.participants.toLocaleString('pt-BR')} hint="registros disponíveis para análise" />
      <StatCard label="Média Matemática" value={summary.means.MT.toFixed(1)} hint={`ENEM ${year}`} />
      <StatCard label="Média Linguagens" value={summary.means.LC.toFixed(1)} hint={`ENEM ${year}`} />
      <StatCard label="Média Redação" value={summary.means.REDACAO.toFixed(1)} hint={`ENEM ${year}`} />
    </section>
  )
}
