// As cinco áreas do ENEM, na ordem da prova. Cada área tem uma cor fixa, usada igual em
// campos, cartões, radar e imagem de compartilhamento, para a pessoa aprender o código.
export const AREAS = [
  { code: 'CN', label: 'Ciências da Natureza', short: 'Natureza', color: '#2f8f3a' },
  { code: 'CH', label: 'Ciências Humanas', short: 'Humanas', color: '#c0398a' },
  { code: 'LC', label: 'Linguagens e Códigos', short: 'Linguagens', color: '#6d4bd8' },
  { code: 'MT', label: 'Matemática', short: 'Matemática', color: '#1f5fd1' },
  { code: 'REDACAO', label: 'Redação', short: 'Redação', color: '#0f766e' },
]

export const AREA_BY_CODE = Object.fromEntries(AREAS.map((area) => [area.code, area]))

export const DEFAULT_SCORES = { CN: '', CH: '', LC: '', MT: '', REDACAO: '' }

// Edições em que nota, estado e questionário socioeconômico podem ser ligados. A partir de 2024
// o INEP publica os microdados anonimizados (LGPD) e esses recortes deixam de existir.
export const FIRST_LINKED_YEAR = 2018
export const LAST_LINKED_YEAR = 2023
export const isLinkedYear = (year) => year >= FIRST_LINKED_YEAR && year <= LAST_LINKED_YEAR
