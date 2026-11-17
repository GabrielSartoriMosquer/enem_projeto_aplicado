// Carregamento no estilo cartão-resposta: cinco bolinhas que se preenchem em sequência.
export default function Loading({ label = 'Carregando dados…' }) {
  return (
    <div className="loading-shell" role="status" aria-live="polite">
      <span className="loading-bubbles" aria-hidden="true">
        {['A', 'B', 'C', 'D', 'E'].map((letter, index) => <i key={letter} style={{ '--i': index }}>{letter}</i>)}
      </span>
      <span className="loading-label">{label}</span>
    </div>
  )
}
