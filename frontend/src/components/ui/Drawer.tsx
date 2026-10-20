import { useEffect, useId, useRef, type ReactNode } from 'react'
import { Icon } from './Icon'

interface DrawerProps {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  /** Extra keyboard handling (e.g. arrow navigation between records). */
  onKeyDown?: (event: KeyboardEvent) => void
}

const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'

/** Modal side panel: focus moves in on open, is trapped while open, and returns on close. Esc closes. */
export function Drawer({ title, onClose, children, footer, onKeyDown }: DrawerProps) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const handlers = useRef({ onClose, onKeyDown })
  handlers.current = { onClose, onKeyDown }

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    panelRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus()

    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        handlers.current.onClose()
        return
      }
      if (event.key === 'Tab' && panelRef.current) {
        const nodes = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
        if (!nodes.length) return
        const first = nodes[0]
        const last = nodes[nodes.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
        return
      }
      handlers.current.onKeyDown?.(event)
    }

    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      previouslyFocused?.focus?.()
    }
  }, [])

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={panelRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="drawer__head">
          <h2 id={titleId} className="drawer__title">{title}</h2>
          <button type="button" className="btn btn--ghost btn--icon" onClick={onClose} aria-label="Fechar" data-autofocus>
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="drawer__body">{children}</div>
        {footer && <div className="drawer__foot">{footer}</div>}
      </div>
    </>
  )
}
