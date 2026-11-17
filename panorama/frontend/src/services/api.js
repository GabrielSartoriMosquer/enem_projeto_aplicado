const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// Mostrada quando o servidor não responde (fora do ar ou sem internet).
const OFFLINE_MESSAGE = 'Nosso serviço está temporariamente indisponível. Verifique sua conexão com a internet e tente novamente em alguns instantes.'

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch (_) {
    throw new Error(OFFLINE_MESSAGE)
  }
  if (!response.ok) {
    let message = 'Não foi possível concluir a consulta.'
    try {
      const body = await response.json()
      message = body.detail || message
    } catch (_) {
      // Sem JSON num erro 5xx: quem respondeu foi o proxy do Vite, não a API (API desligada).
      if (response.status >= 500) message = OFFLINE_MESSAGE
    }
    throw new Error(message)
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  years: () => request('/meta/years'),
  options: (year) => request(`/meta/options?year=${year}`),
  summary: (year) => request(`/analysis/summary?year=${year}`),
  percentile: (year, scores) => request('/analysis/percentile', {
    method: 'POST', body: JSON.stringify({ year, scores }),
  }),
  socioeconomic: (year, area, dimension) => request(
    `/analysis/socioeconomic?year=${year}&area=${area}&dimension=${dimension}`,
  ),
  regionSchool: (year, area, schoolType = '') => request(
    `/analysis/region-school?year=${year}&area=${area}${schoolType ? `&school_type=${schoolType}` : ''}`,
  ),
  essay: (year, score) => request('/analysis/essay', {
    method: 'POST', body: JSON.stringify({ year, score: Number(score) }),
  }),
}
