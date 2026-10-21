import { useState } from 'react'
import { useAlertSettings } from '../../hooks/useCriticalAlerts'
import { showNotification } from '../../lib/alerts'
import { Icon } from '../ui/Icon'

/** Opt-in for browser notifications when a watched file gets CRITICAL lines. */
export function WatchAlerts() {
  const { permission, enabled, enable, disable } = useAlertSettings()
  const [asking, setAsking] = useState(false)
  const [tested, setTested] = useState<boolean | null>(null)

  if (permission === 'unsupported') {
    return <p className="card__hint watch-alerts">Alertas indisponíveis: o navegador só permite notificações em HTTPS ou em localhost.</p>
  }
  if (permission === 'denied') {
    return (
      <p className="card__hint watch-alerts">
        Notificações bloqueadas para este site. Libere nas permissões do navegador e recarregue a página para receber alertas.
      </p>
    )
  }

  const ask = async () => {
    setAsking(true)
    try {
      await enable()
    } finally {
      setAsking(false)
    }
  }
  return (
    <div className="watch-alerts" role="group" aria-label="Alertas de erros críticos">
      <Icon name="bell" />
      <span className="card__hint" aria-live="polite">
        {enabled
          ? 'Alertas ativos: você recebe uma notificação quando um arquivo observado registra um log CRITICAL, enquanto o GTLog estiver aberto em alguma aba.'
          : 'Receba uma notificação do navegador quando um arquivo observado registrar um log CRITICAL.'}
      </span>
      {enabled ? (
        <>
          <button type="button" className="btn btn--sm" onClick={() => setTested(showNotification('GTLog: teste de alerta', { body: 'Se você está vendo isto, os alertas de erros críticos vão aparecer.', tag: 'gtlog-test' }))}>
            Testar
          </button>
          <button type="button" className="btn btn--sm btn--ghost" onClick={disable}>Desativar alertas</button>
        </>
      ) : (
        <button type="button" className="btn btn--sm" onClick={ask} disabled={asking}>Ativar alertas</button>
      )}
      {enabled && tested !== null && (
        <p className="card__hint watch-alerts__test" role="status">
          {tested
            ? 'Notificação de teste enviada. Não apareceu? No Mac, libere o navegador em Ajustes do Sistema › Notificações e confira se o Foco (Não Perturbe) está desligado. No Safari, veja também Ajustes › Sites › Notificações. Os alertas também aparecem no canto da página.'
            : 'O navegador recusou a notificação. Os alertas continuam aparecendo no canto da página enquanto ela estiver aberta.'}
        </p>
      )}
    </div>
  )
}
