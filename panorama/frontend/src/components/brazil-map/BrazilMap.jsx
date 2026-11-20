import { useLayoutEffect, useRef, useState } from 'react'
import brazil from '@svg-maps/brazil'

function stateTone(mean, min, max) {
  if (mean === null || mean === undefined) return 'no-data'
  if (max === min) return 'mid'
  const ratio = (mean - min) / (max - min)
  if (ratio > 0.75) return 'tone-4'
  if (ratio > 0.5) return 'tone-3'
  if (ratio > 0.25) return 'tone-2'
  return 'tone-1'
}

// Ajustes do centro das siglas onde o centro da área cai em cima de outra sigla.
const LABEL_OFFSETS = { GO: [-14, 6], DF: [3, -1] }

const formatMean = (value) => value.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

// O estado só é selecionado no clique (ou Enter/Espaço). Passar o mouse apenas destaca e mostra
// um balão com o nome e o valor, para não trocar a seleção ao atravessar o mapa até o centro.
// O valor de cada estado vem em `mean`. Por padrão é uma média de notas; outras áreas passam
// `formatValue`, `valueLabel` e `description` (ex.: percentual de inscritos sem internet).
export default function BrazilMap({
  states, selectedUf, onSelect, areaLabel,
  formatValue = formatMean, valueLabel = 'Média', description,
}) {
  const stageRef = useRef(null)
  const pathRefs = useRef({})
  const [labelPositions, setLabelPositions] = useState({})
  const [hover, setHover] = useState(null)
  const byUf = Object.fromEntries(states.map((state) => [state.uf, state]))
  const values = states.filter((state) => state.mean !== null && state.mean !== undefined).map((state) => state.mean)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 0

  useLayoutEffect(() => {
    const nextPositions = {}
    brazil.locations.forEach((location) => {
      const path = pathRefs.current[location.id]
      if (!path) return
      const bounds = path.getBBox()
      nextPositions[location.id.toUpperCase()] = {
        x: bounds.x + (bounds.width / 2),
        y: bounds.y + (bounds.height / 2),
      }
    })
    setLabelPositions(nextPositions)
  }, [])

  const trackHover = (uf, event) => {
    const box = stageRef.current?.getBoundingClientRect()
    if (!box) return
    setHover({ uf, x: event.clientX - box.left, y: event.clientY - box.top })
  }

  // O SVG desenha na ordem do DOM: o estado selecionado vai por último para a borda dele
  // não ficar escondida embaixo dos vizinhos. O DF fica sempre no topo, porque está dentro de
  // Goiás e sumiria embaixo dele.
  const layer = (location) => {
    const uf = location.id.toUpperCase()
    if (uf === 'DF') return 2
    return uf === selectedUf ? 1 : 0
  }
  const ordered = [...brazil.locations].sort((left, right) => layer(left) - layer(right))

  const hovered = hover ? byUf[hover.uf] : null

  return (
    <div className="map-stage" ref={stageRef}>
      <svg className="brazil-map" viewBox={brazil.viewBox} role="group" aria-label={`${description || `Mapa do Brasil com a média de ${areaLabel} por estado`}. Clique em um estado para ver os detalhes.`}>
        {ordered.map((location) => {
          const uf = location.id.toUpperCase()
          const state = byUf[uf]
          const name = state?.name || location.name
          const hasData = state && state.mean !== null && state.mean !== undefined
          return (
            <path
              key={location.id}
              ref={(node) => { pathRefs.current[location.id] = node }}
              d={location.path}
              className={`map-state ${stateTone(state?.mean, min, max)}${selectedUf === uf ? ' selected' : ''}`}
              tabIndex="0"
              role="button"
              aria-pressed={selectedUf === uf}
              aria-label={`${name}, ${hasData ? `${valueLabel.toLowerCase()} ${formatValue(state.mean)}` : 'sem dados nesta edição'}`}
              onMouseMove={(event) => trackHover(uf, event)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect(uf)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelect(uf)
                }
              }}
            />
          )
        })}
        <g className="map-labels" aria-hidden="true">
          {Object.entries(labelPositions).map(([uf, position]) => (
            <text key={uf} x={position.x + (LABEL_OFFSETS[uf]?.[0] || 0)} y={position.y + (LABEL_OFFSETS[uf]?.[1] || 0)} className={selectedUf === uf ? 'map-uf-label selected' : 'map-uf-label'}>{uf}</text>
          ))}
        </g>
      </svg>

      {hovered && (
        <div className="map-hover" style={{ left: hover.x, top: hover.y }} aria-hidden="true">
          <strong>{hovered.name}</strong>
          <span>{hovered.mean === null || hovered.mean === undefined ? 'Sem dados' : `${valueLabel} ${formatValue(hovered.mean)}`}</span>
        </div>
      )}

      <div className="map-legend" aria-label="Legenda do mapa">
        <span className="map-legend-scale">
          <span>{values.length ? formatValue(min) : '—'}</span>
          <i className="legend-ramp" />
          <span>{values.length ? formatValue(max) : '—'}</span>
        </span>
        <span className="map-legend-note"><i className="legend-swatch no-data" /> sem dados</span>
      </div>
    </div>
  )
}
