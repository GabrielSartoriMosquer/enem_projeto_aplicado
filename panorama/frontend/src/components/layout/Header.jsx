import { ChevronDown, Home, PenLine, Map, Users, BookOpen } from 'lucide-react'

const ICONS = { overview: Home, panorama: PenLine, region: Map, socio: Users, methodology: BookOpen }

// Cabeçalho com o único seletor de edição do site. No celular, os links vão para uma barra
// fixa embaixo da tela, ao alcance do polegar.
export default function Header({ sections, activeSection, onNavigate, year, years, onYearChange }) {
  const links = (className) => sections.map((item) => {
    const Icon = ICONS[item.id]
    const isActive = activeSection === item.id
    return (
      <a
        key={item.id}
        href={`#${item.id}`}
        className={isActive ? `${className} active` : className}
        aria-current={isActive ? 'true' : undefined}
        onClick={(event) => {
          event.preventDefault()
          onNavigate(item.id)
        }}
      >
        {className === 'tab-link' && <Icon size={20} aria-hidden="true" />}
        <span>{item.label}</span>
      </a>
    )
  })

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand-block" href="#overview" onClick={(event) => { event.preventDefault(); onNavigate('overview') }} aria-label="Panorama ENEM, ir para o início">
            <span className="brand-mark" aria-hidden="true">P</span>
            <span className="brand-name">Panorama ENEM</span>
          </a>

          <nav className="main-nav" aria-label="Seções">{links('nav-link')}</nav>

          <label className="header-year">
            <span>Edição</span>
            <select value={year || ''} onChange={(event) => onYearChange(Number(event.target.value))} aria-label="Edição do ENEM">
              {!years.length && <option value={year || ''}>{year || '…'}</option>}
              {years.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <ChevronDown size={16} aria-hidden="true" />
          </label>
        </div>
      </header>

      <nav className="tab-bar" aria-label="Seções">{links('tab-link')}</nav>
    </>
  )
}
