import { Link } from 'react-router-dom'
import type { TopError } from '../../api/types'
import { formatDateTime, formatNumber, formatRelative } from '../../lib/format'

interface TopErrorsProps {
  items: TopError[]
  /** Link to the logs page searching for this message. */
  hrefFor: (message: string) => string
}

export function TopErrors({ items, hrefFor }: TopErrorsProps) {
  const max = Math.max(...items.map((item) => item.count), 1)
  return (
    <table className="top-errors">
      <thead>
        <tr>
          <th scope="col">Mensagem (números agrupados como #)</th>
          <th scope="col" className="num">Ocorrências</th>
          <th scope="col" className="num col-last">Última vez</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => {
          const href = hrefFor(item.message)
          return (
            <tr key={item.message}>
              <td>
                <Link className="top-errors__link" to={href} title="Ver logs com esta mensagem">
                  <span className="top-errors__msg">{item.message}</span>
                  <span className="top-errors__bar" style={{ width: `${(item.count / max) * 100}%` }} aria-hidden="true" />
                </Link>
              </td>
              <td className="num">
                <Link className="top-errors__link" to={href} tabIndex={-1} aria-hidden="true">{formatNumber(item.count)}</Link>
              </td>
              <td className="num col-last">
                <Link className="top-errors__link" to={href} tabIndex={-1} aria-hidden="true">
                  <time dateTime={item.last_seen} title={formatDateTime(item.last_seen)}>{formatRelative(item.last_seen)}</time>
                </Link>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
