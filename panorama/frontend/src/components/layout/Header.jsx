import React from 'react'
import { Menu, X, Database, ChevronDown } from 'lucide-react'

const navItems = [
  { id: 'overview', label: 'Visão Geral' },
  { id: 'panorama', label: 'Meu Panorama' },
  { id: 'percentile', label: 'Minha Posição' },
  { id: 'socio', label: 'Socioeconômico' },
  { id: 'region', label: 'Estados e Escolas' },
  { id: 'essay', label: 'Redação' },
  { id: 'methodology', label: 'Metodologia' },
]

export default function Header({ source, activeSection, onNavigate, year, years, onYearChange }) {
  const [menuOpen, setMenuOpen] = React.useState(false)

  const navigate = (id) => {
    onNavigate(id)
    setMenuOpen(false)
  }

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <button className="brand-block" type="button" onClick={() => navigate('overview')} aria-label="Ir para visão geral">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span className="brand-copy">
            <span className="brand-eyebrow">Panorama</span>
            <strong className="brand-name">ENEM</strong>
          </span>
        </button>

        <nav className={menuOpen ? 'main-nav open' : 'main-nav'} aria-label="Navegação principal">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.id}
              className={activeSection === item.id ? 'nav-link active' : 'nav-link'}
              onClick={() => navigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="header-actions">
          <div className="source-pill" aria-live="polite"><Database size={14} /> {source || 'carregando…'}</div>
          <label className="header-year">
            <span>Edição</span>
            <select value={year} onChange={(event) => onYearChange(Number(event.target.value))} aria-label="Selecionar edição">
              {years.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </label>
          <button className="menu-toggle" type="button" onClick={() => setMenuOpen((value) => !value)} aria-expanded={menuOpen} aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}>
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  )
}
