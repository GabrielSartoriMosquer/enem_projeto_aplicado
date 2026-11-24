// Fundo decorativo do topo: um trecho de cartão-resposta do ENEM, com questões numeradas e
// uma alternativa marcada por linha. A sequência de marcações é fixa (não muda a cada render).
const MARKS = [2, 0, 3, 1, 4, 2, 2, 0, 3, 4, 1, 3, 0, 2]
const LETTERS = ['A', 'B', 'C', 'D', 'E']

export default function AnswerSheet({ start = 91 }) {
  const rowHeight = 34
  return (
    <svg className="answer-sheet" viewBox={`0 0 230 ${MARKS.length * rowHeight}`} aria-hidden="true" focusable="false">
      {MARKS.map((mark, row) => (
        <g key={row} transform={`translate(0 ${row * rowHeight + 17})`}>
          <text x="0" y="5" className="answer-sheet-number">{start + row}</text>
          {LETTERS.map((letter, column) => (
            <g key={letter} transform={`translate(${54 + column * 36} 0)`}>
              <circle r="12" className={column === mark ? 'answer-sheet-bubble marked' : 'answer-sheet-bubble'} />
              {column !== mark && <text y="4.5" className="answer-sheet-letter">{letter}</text>}
            </g>
          ))}
        </g>
      ))}
    </svg>
  )
}
