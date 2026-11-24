import { filledBubbles } from '../../utils/percentile'

// O percentil desenhado como uma linha do cartão-resposta: 10 bolinhas, cada uma vale 10% dos
// participantes. As bolinhas se preenchem em sequência quando o resultado aparece.
export default function BubbleScale({ percentile, color, label }) {
  const filled = filledBubbles(percentile)
  return (
    <span className="bubble-scale" style={{ '--area': color }} role="img" aria-label={label || `${filled} de 10 bolinhas preenchidas`}>
      {Array.from({ length: 10 }, (_, index) => (
        <i key={index} className={index < filled ? 'filled' : ''} style={{ '--i': index }} />
      ))}
    </span>
  )
}
