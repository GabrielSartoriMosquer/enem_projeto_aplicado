// "Como funciona" em linguagem do dia a dia. Os três passos são uma sequência de verdade, por
// isso são numerados. Os termos técnicos ficam numa nota pequena para quem quiser saber.
const STEPS = [
  ['Pegamos os dados oficiais', 'O INEP publica as notas de todos os participantes de cada edição, sem nome nem documento.'],
  ['Limpamos e organizamos', 'Tiramos registros com nota zero em alguma prova objetiva e padronizamos os oito anos, de 2018 a 2025.'],
  ['Comparamos a sua nota', 'Sua nota é comparada só com quem fez a mesma edição, porque a prova muda de dificuldade a cada ano.'],
]

const TERMS = [
  ['Percentil', 'A porcentagem de participantes com nota menor ou igual à sua. Percentil 80 quer dizer "melhor que 8 em cada 10".'],
  ['Média', 'A soma de todas as notas dividida pelo número de participantes. É o ponto de referência da edição.'],
  ['Desvio padrão', 'O quanto as notas se espalham em volta da média. Quanto maior, mais diferentes as notas são entre si.'],
  ['Distância da média', 'Também chamada de z-score: quantos desvios padrão sua nota está acima ou abaixo da média.'],
]

export default function Methodology() {
  return (
    <section id="methodology" className="methodology-panel">
      <div className="section-heading">
        <h2>Como funciona</h2>
        <p>Tudo o que você vê aqui vem dos microdados públicos do ENEM.</p>
      </div>

      <ol className="methodology-flow">
        {STEPS.map(([title, text], index) => (
          <li key={title} className="flow-step">
            <span className="flow-number" aria-hidden="true">{index + 1}</span>
            <div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          </li>
        ))}
      </ol>

      <h3 className="terms-title">O que cada número quer dizer</h3>
      <dl className="methodology-cards">
        {TERMS.map(([term, text]) => (
          <div key={term} className="method-card">
            <dt>{term}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>

      <div className="disclaimer-box">
        <strong>Relação não é causa</strong>
        <p>As comparações mostram o que aconteceu nos dados de cada edição. Elas não explicam por que uma nota foi maior ou menor.</p>
      </div>
      <p className="tech-note">Para quem quiser os detalhes técnicos: os dados passam por um ETL em Python, ficam em Parquet e são consultados com DuckDB por uma API em FastAPI.</p>
    </section>
  )
}
