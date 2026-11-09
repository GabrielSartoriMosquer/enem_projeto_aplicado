const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    let message = 'Não foi possível concluir a consulta.'
    try {
      const body = await response.json()
      message = body.detail || message
    } catch (_) {
      // mantém mensagem padrão
    }
    throw new Error(message)
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  years: () => request('/meta/years'),
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
