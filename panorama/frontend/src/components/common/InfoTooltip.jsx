export default function InfoTooltip({ label, text }) {
  return (
    <span className="tooltip-wrap">
      <span className="tooltip-trigger" tabIndex={0} aria-label={`${label}: ${text}`} title={text}>?</span>
      <span className="tooltip-text">{text}</span>
    </span>
  )
}
