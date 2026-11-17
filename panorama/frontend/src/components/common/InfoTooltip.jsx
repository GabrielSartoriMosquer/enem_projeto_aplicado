import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'

const EDGE = 12

// Ícone "i" com um balão de explicação. Abre com o mouse, com o foco do teclado e com toque
// (para funcionar no celular). Fecha com Esc ou tocando fora. O balão só existe enquanto está
// aberto e é empurrado para dentro da tela quando ficaria cortado na borda.
// align="center" abre centralizado sob o ícone; align="right" alinha pela direita.
export default function InfoTooltip({ label, text, align = 'center' }) {
  const tooltipId = useId()
  const rootRef = useRef(null)
  const bubbleRef = useRef(null)
  const [pinned, setPinned] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [shift, setShift] = useState(0)
  const open = pinned || hovered

  useEffect(() => {
    if (!pinned) return undefined
    const close = (event) => {
      if (event.type === 'keydown' ? event.key === 'Escape' : !rootRef.current?.contains(event.target)) setPinned(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
    }
  }, [pinned])

  useLayoutEffect(() => {
    if (!open || !bubbleRef.current) {
      setShift(0)
      return
    }
    const box = bubbleRef.current.getBoundingClientRect()
    const width = document.documentElement.clientWidth
    const base = box.left - shift
    const right = base + box.width
    if (base < EDGE) setShift(EDGE - base)
    else if (right > width - EDGE) setShift(width - EDGE - right)
    else setShift(0)
    // `shift` fica fora das dependências: o cálculo desconta o deslocamento atual.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  return (
    <span
      ref={rootRef}
      className={open ? 'info-tip open' : 'info-tip'}
      data-align={align}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        className="info-tip-trigger"
        aria-label={`Sobre ${label}`}
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        onClick={() => {
          if (open) {
            setPinned(false)
            setHovered(false)
          } else setPinned(true)
        }}
        // Só o foco por teclado abre o balão: no toque, o clique logo depois cuidaria disso e
        // fecharia o balão que o foco acabou de abrir.
        onFocus={(event) => { if (event.target.matches(':focus-visible')) setHovered(true) }}
        onBlur={() => setHovered(false)}
      >i</button>
      {open && (
        <span ref={bubbleRef} className="info-tip-text" role="tooltip" id={tooltipId} style={{ '--shift': `${shift}px` }}>{text}</span>
      )}
    </span>
  )
}
