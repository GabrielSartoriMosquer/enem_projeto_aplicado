import { useEffect, useRef, useState } from 'react'
import { AREA_BY_CODE } from '../../constants/areas'
import { filledBubbles, percentilePhrase } from '../../utils/percentile'

const WIDTH = 1080
const HEIGHT = 1920
const NAVY = '#071e33'
const MINT = '#22c7b8'

// Desenhado direto no canvas (e não como SVG convertido em imagem), porque assim o texto usa as
// fontes já carregadas na página. Formato 9:16, o tamanho dos stories.
async function drawCard(canvas, year, results, source) {
  if (document.fonts?.load) {
    await Promise.all([
      document.fonts.load('700 72px "Space Grotesk"'),
      document.fonts.load('500 36px "DM Sans"'),
      document.fonts.load('700 36px "DM Sans"'),
    ]).catch(() => {})
  }
  const ctx = canvas.getContext('2d')
  canvas.width = WIDTH
  canvas.height = HEIGHT
  ctx.fillStyle = NAVY
  ctx.fillRect(0, 0, WIDTH, HEIGHT)

  // Trecho de cartão-resposta no canto, como no topo do site.
  ctx.save()
  ctx.globalAlpha = 0.16
  ctx.strokeStyle = MINT
  ctx.lineWidth = 3
  const marks = [2, 0, 3, 1, 4, 2]
  marks.forEach((mark, row) => {
    for (let column = 0; column < 5; column += 1) {
      ctx.beginPath()
      ctx.arc(700 + column * 72, 110 + row * 72, 24, 0, Math.PI * 2)
      if (column === mark) { ctx.fillStyle = MINT; ctx.fill() } else ctx.stroke()
    }
  })
  ctx.restore()

  // Marca
  ctx.fillStyle = MINT
  ctx.beginPath(); ctx.arc(116, 130, 40, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = NAVY
  ctx.font = '700 46px "Space Grotesk", sans-serif'
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  ctx.fillText('P', 116, 132)
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = '#ffffff'
  ctx.font = '700 38px "Space Grotesk", sans-serif'
  ctx.fillText('Panorama ENEM', 176, 144)

  const sorted = [...results].filter((item) => item.percentile !== null).sort((a, b) => b.percentile - a.percentile)
  const best = sorted[0]

  ctx.fillStyle = '#b9d1d8'
  ctx.font = '500 40px "DM Sans", sans-serif'
  ctx.fillText(`Meu resultado no ENEM ${year}`, 76, 400)
  if (best) {
    ctx.fillStyle = '#ffffff'
    ctx.font = '700 76px "Space Grotesk", sans-serif'
    wrapText(ctx, percentilePhrase(best.percentile), 76, 500, 930, 86)
    ctx.fillStyle = '#b9d1d8'
    ctx.font = '500 40px "DM Sans", sans-serif'
    ctx.fillText(`em ${best.label}`, 76, 700)
  }

  let y = 860
  sorted.forEach((item) => {
    const color = AREA_BY_CODE[item.area]?.color || MINT
    ctx.fillStyle = lighten(color)
    ctx.font = '700 40px "DM Sans", sans-serif'
    ctx.fillText(item.label, 76, y)
    ctx.fillStyle = '#d6e6ea'
    ctx.font = '500 32px "DM Sans", sans-serif'
    ctx.fillText(percentilePhrase(item.percentile), 76, y + 48)
    const filled = filledBubbles(item.percentile)
    for (let index = 0; index < 10; index += 1) {
      ctx.beginPath()
      ctx.arc(96 + index * 62, y + 108, 22, 0, Math.PI * 2)
      if (index < filled) { ctx.fillStyle = lighten(color); ctx.fill() } else { ctx.strokeStyle = 'rgba(214, 230, 234, .35)'; ctx.lineWidth = 3; ctx.stroke() }
    }
    y += 200
  })

  ctx.strokeStyle = 'rgba(214, 230, 234, .2)'
  ctx.lineWidth = 2
  ctx.beginPath(); ctx.moveTo(76, HEIGHT - 190); ctx.lineTo(WIDTH - 76, HEIGHT - 190); ctx.stroke()
  ctx.fillStyle = '#9fc6ca'
  ctx.font = '500 32px "DM Sans", sans-serif'
  ctx.fillText(source === 'demo' ? 'Dados de demonstração, não oficiais' : 'Calculado com os microdados oficiais do INEP', 76, HEIGHT - 120)
  ctx.fillText('Cada bolinha vale 10% dos participantes', 76, HEIGHT - 70)
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = text.split(' ')
  let line = ''
  let currentY = y
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, currentY)
      line = word
      currentY += lineHeight
    } else line = test
  })
  ctx.fillText(line, x, currentY)
}

// Clareia a cor da área para ela ter contraste sobre o fundo azul-marinho.
function lighten(hex) {
  const value = parseInt(hex.slice(1), 16)
  const mix = (channel) => Math.round(channel + (255 - channel) * 0.35)
  return `rgb(${mix(value >> 16)}, ${mix((value >> 8) & 255)}, ${mix(value & 255)})`
}

const canvasToBlob = (canvas) => new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))

export default function ShareCard({ year, results, source }) {
  const canvasRef = useRef(null)
  const [copied, setCopied] = useState(false)
  const fileName = `meu-panorama-enem-${year}.png`

  useEffect(() => {
    if (canvasRef.current) drawCard(canvasRef.current, year, results, source)
  }, [year, results, source])

  const download = async () => {
    const blob = await canvasToBlob(canvasRef.current)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
    URL.revokeObjectURL(url)
  }

  const share = async () => {
    const blob = await canvasToBlob(canvasRef.current)
    const file = new File([blob], fileName, { type: 'image/png' })
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      try { await navigator.share({ title: `Meu Panorama ENEM ${year}`, files: [file] }) } catch (_) { /* compartilhamento cancelado */ }
    } else {
      await download()
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2200)
    } catch (_) {
      window.prompt('Copie o link do seu resultado:', window.location.href)
    }
  }

  return (
    <div className="share-card-panel">
      <canvas ref={canvasRef} className="share-card-preview" width={WIDTH} height={HEIGHT} role="img" aria-label="Prévia da imagem para compartilhar" />
      <div className="share-card-copy">
        <h3>Mostre seu resultado</h3>
        <p>A imagem tem o tamanho dos stories. O link abre o site já com as suas notas, para você voltar depois ou mandar para alguém.</p>
        <div className="share-card-actions">
          <button type="button" className="button button-primary" onClick={share}>Compartilhar imagem</button>
          <button type="button" className="button button-outline" onClick={download}>Baixar imagem</button>
          <button type="button" className="button button-outline" onClick={copyLink} aria-live="polite">{copied ? 'Link copiado' : 'Copiar link'}</button>
        </div>
      </div>
    </div>
  )
}
