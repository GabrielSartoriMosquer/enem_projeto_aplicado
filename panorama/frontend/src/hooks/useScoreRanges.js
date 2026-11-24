import { useEffect, useState } from 'react'
import { api } from '../services/api'

// Menor e maior nota registrada por área na edição ({ CN: { min, max }, ... }).
// Pela TRI, as provas objetivas nunca chegam a 1000 e o teto muda a cada ano,
// então os campos de nota usam estes limites em vez de 0–1000.
export function useScoreRanges(year) {
  const [ranges, setRanges] = useState(null)

  useEffect(() => {
    if (!year) return undefined
    let active = true
    api.options(year)
      .then((payload) => { if (active) setRanges(payload?.score_ranges || null) })
      .catch(() => { if (active) setRanges(null) })
    return () => { active = false }
  }, [year])

  return ranges
}

// Áreas cuja nota digitada está fora da menor/maior nota registrada na edição.
export function invalidAreas(scores, ranges) {
  if (!ranges) return []
  return Object.entries(scores)
    .filter(([area, value]) => {
      const limits = ranges[area]
      if (!limits || value === '' || value === null) return false
      const score = Number(value)
      return Number.isNaN(score) || score < limits.min || score > limits.max
    })
    .map(([area]) => area)
}

// Validação das notas que só aparece depois que a pessoa tenta enviar o formulário.
// O aviso fica visível até todas as notas ficarem válidas; depois disso, volta a esperar
// um novo envio para aparecer de novo.
export function useScoreValidation(year, scores) {
  const ranges = useScoreRanges(year)
  const [attempted, setAttempted] = useState(false)
  const invalid = invalidAreas(scores, ranges)

  useEffect(() => {
    if (attempted && invalid.length === 0) setAttempted(false)
  }, [attempted, invalid.length])

  const shownInvalid = attempted ? invalid : []
  // Chamar no submit: devolve true se pode enviar; se não, passa a mostrar o aviso.
  const canSubmit = () => {
    if (invalid.length) {
      setAttempted(true)
      return false
    }
    return true
  }

  return { ranges, invalid: shownInvalid, canSubmit }
}

export const formatScore = (value) => Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
