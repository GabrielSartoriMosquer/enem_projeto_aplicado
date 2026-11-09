import { useLayoutEffect, useRef, useState } from 'react'
import brazil from '@svg-maps/brazil'

function stateTone(mean, min, max) {
  if (mean === null || mean === undefined) return 'no-data'
  if (max === min) return 'has-data'
  const ratio = (mean - min) / (max - min)
  if (ratio > 0.66) return 'high'
  if (ratio > 0.33) return 'mid'
  return 'low'
}

export default function BrazilMap({ states, selectedUf, onSelect, areaLabel, year }) {
  const pathRefs = useRef({})
  const [labelPositions, setLabelPositions] = useState({})
  const byUf = Object.fromEntries(states.map((state) => [state.uf, state]))
  const values = states.filter((state) => state.mean !== null && state.mean !== undefined).map((state) => state.mean)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 0
  const selected = selectedUf ? byUf[selectedUf] : null

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

  return (
    <div className="map-stage">
      <div className="map-tooltip" aria-live="polite">
        {selected ? (
          <>
            <strong>{selected.name} <small>{selected.uf}</small></strong>
            <span>{selected.mean === null ? 'Sem dados nesta edição' : `Média: ${selected.mean.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`}</span>
            <span>{selected.n ? `Participantes: ${selected.n.toLocaleString('pt-BR')}` : 'Participantes: 0'}</span>
            <span>{areaLabel} • ENEM {year}</span>
          </>
        ) : <span>Selecione uma UF para ver os dados reais.</span>}
      </div>
      <svg className="brazil-map" viewBox={brazil.viewBox} role="img" aria-label={`Mapa do Brasil por média de ${areaLabel}`}>
        {brazil.locations.map((location) => {
          const uf = location.id.toUpperCase()
          const state = byUf[uf]
          const selectedClass = selectedUf === uf ? ' selected' : ''
          return (
            <path
              key={location.id}
              ref={(node) => { pathRefs.current[location.id] = node }}
              d={location.path}
              className={`map-state ${stateTone(state?.mean, min, max)}${selectedClass}`}
              tabIndex="0"
              role="button"
              aria-label={`${state?.name || location.name}, ${state?.mean === null || !state ? 'sem dados nesta edição' : `média ${state.mean}`}`}
              onMouseEnter={() => onSelect(uf)}
              onFocus={() => onSelect(uf)}
              onClick={() => onSelect(uf)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onSelect(uf)
              }}
            />
          )
        })}
        <g className="map-labels" aria-hidden="true">
          {Object.entries(labelPositions).map(([uf, position]) => (
            <text key={uf} x={position.x} y={position.y} className="map-uf-label">{uf}</text>
          ))}
        </g>
      </svg>
      <div className="map-legend" aria-label="Legenda do mapa">
        <span><i className="legend-swatch low" /> menor média</span>
        <span><i className="legend-swatch high" /> maior média</span>
        <span><i className="legend-swatch no-data" /> sem dados</span>
      </div>
    </div>
  )
}
