export default function ErrorState({ message, onRetry, onChangeSource }) {
  return (
    <div className="state-card error-card" role="alert">
      <div className="state-icon">!</div>
      <div>
        <h3>Não conseguimos carregar os dados desta edição.</h3>
        <p>{message}</p>
      </div>
      <div className="state-actions">
        {onRetry && <button type="button" className="button button-primary" onClick={onRetry}>Tentar novamente</button>}
        {onChangeSource && <button type="button" className="button button-secondary" onClick={onChangeSource}>Trocar edição</button>}
      </div>
    </div>
  )
}
