import { formatNumber, formatTopPercent } from '../../utils/percentile'

function escapeXml(value) {
  return String(value).replace(/[<>&'"]/g, (character) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' })[character])
}

function buildSvg(year, results, source) {
  const sorted = [...results].sort((a, b) => (a.percentile ?? -1) - (b.percentile ?? -1)).slice(0, 4)
  const rows = sorted.map((item, index) => `
    <text x="92" y="${450 + index * 112}" fill="#9fc6ca" font-family="DM Sans, sans-serif" font-size="22">${escapeXml(item.label)}</text>
    <text x="92" y="${485 + index * 112}" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="34" font-weight="700">${escapeXml(formatTopPercent(item.percentile))}</text>
  `).join('')
  const best = [...results].sort((a, b) => (b.percentile ?? -1) - (a.percentile ?? -1))[0]
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
    <rect width="1080" height="1350" fill="#071e33"/>
    <circle cx="920" cy="120" r="270" fill="none" stroke="#22c7b8" stroke-opacity=".18" stroke-width="2"/>
    <circle cx="920" cy="120" r="205" fill="none" stroke="#22c7b8" stroke-opacity=".12" stroke-width="2"/>
    <rect x="72" y="72" width="72" height="72" rx="18" fill="#22c7b8"/>
    <text x="108" y="122" text-anchor="middle" fill="#071e33" font-family="Space Grotesk, sans-serif" font-size="42" font-weight="700">P</text>
    <text x="174" y="101" fill="#90c8cd" font-family="DM Sans, sans-serif" font-size="18" font-weight="700" letter-spacing="4">PANORAMA</text>
    <text x="174" y="133" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="31" font-weight="700">ENEM</text>
    <text x="92" y="250" fill="#22c7b8" font-family="DM Sans, sans-serif" font-size="18" font-weight="700" letter-spacing="4">MEU PANORAMA ENEM</text>
    <text x="92" y="315" fill="#ffffff" font-family="Space Grotesk, sans-serif" font-size="64" font-weight="700">ENEM ${escapeXml(year)}</text>
    <text x="92" y="385" fill="#b9d1d8" font-family="DM Sans, sans-serif" font-size="24">Melhor posicionamento</text>
    <text x="92" y="423" fill="#22c7b8" font-family="Space Grotesk, sans-serif" font-size="38" font-weight="700">${escapeXml(best?.label || 'Indisponível')}</text>
    ${rows}
    <line x1="92" y1="950" x2="988" y2="950" stroke="#34586b"/>
    <text x="92" y="1010" fill="#9fc6ca" font-family="DM Sans, sans-serif" font-size="20">Fonte</text>
    <text x="92" y="1048" fill="#ffffff" font-family="DM Sans, sans-serif" font-size="24" font-weight="700">Panorama ENEM / INEP</text>
    <text x="92" y="1115" fill="#9fc6ca" font-family="DM Sans, sans-serif" font-size="18">${escapeXml(source === 'demo' ? 'Ambiente de demonstração • dados sintéticos' : 'Dados oficiais INEP')}</text>
    <text x="92" y="1260" fill="#6f9aa1" font-family="DM Sans, sans-serif" font-size="17">Posicionamento relativo por percentis</text>
  </svg>`
}

async function svgToPng(svg) {
  const image = new Image()
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  await image.decode()
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1350
  canvas.getContext('2d').drawImage(image, 0, 0)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
}

export default function ShareCard({ year, results, source }) {
  const svg = buildSvg(year, results, source)
  const download = async () => {
    const blob = await svgToPng(svg)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `meu-panorama-enem-${year}.png`
    link.click()
    URL.revokeObjectURL(url)
  }
  const share = async () => {
    const blob = await svgToPng(svg)
    const file = new File([blob], `meu-panorama-enem-${year}.png`, { type: 'image/png' })
    if (navigator.share && (!navigator.canShare || navigator.canShare({ files: [file] }))) {
      await navigator.share({ title: `Meu Panorama ENEM ${year}`, files: [file] })
    } else {
      await download()
    }
  }

  return (
    <div className="share-card-panel">
      <div className="share-card-preview" dangerouslySetInnerHTML={{ __html: svg }} />
      <div className="share-card-actions">
        <button type="button" className="button button-primary" onClick={share}>Compartilhar meu resultado</button>
        <button type="button" className="button button-secondary" onClick={download}>Gerar imagem</button>
      </div>
    </div>
  )
}

export { buildSvg, formatNumber }
