import InfoTooltip from './InfoTooltip'
import { formatScore } from '../../hooks/useScoreRanges'

const TRI_TEXT = 'As provas objetivas são corrigidas pela TRI (Teoria de Resposta ao Item). A nota depende de quais questões você acertou e da dificuldade de cada uma, não só da quantidade de acertos. Por isso a nota máxima fica abaixo de 1000, a mínima fica perto de 300, e as duas mudam a cada edição e área. Os limites são a menor e a maior nota registradas nos microdados do INEP.'

// Aviso das notas inválidas (a lista vem de useScoreValidation, só depois de tentar enviar).
export default function ScoreRangeNote({ year, ranges, scores, invalid, labels }) {
  if (!invalid.length || !ranges) return null
  const objective = invalid.filter((area) => area !== 'REDACAO')
  const tooHigh = objective.some((area) => Number(scores[area]) > ranges[area].max)
  const tooLow = objective.some((area) => Number(scores[area]) < ranges[area].min)

  return (
    <div className="score-range-note" role="alert">
      <strong>{invalid.length > 1 ? 'Essas notas não existem' : 'Essa nota não existe'} no ENEM {year}.</strong>{' '}
      {invalid.map((area, index) => (
        <span key={area}>
          {index > 0 && '; '}
          {labels[area]} vai de {formatScore(ranges[area].min)} a {formatScore(ranges[area].max)}
        </span>
      ))}.
      {tooHigh && ' Nas provas objetivas não dá para tirar 1000, nem acertando todas as questões.'}
      {tooLow && ' Pela forma de correção, mesmo quem acerta poucas questões fica perto de 300.'}
      {objective.length > 0 && <InfoTooltip label="Limites da nota" text={TRI_TEXT} />}
    </div>
  )
}
