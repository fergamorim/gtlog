const WIDTHS = ['92%', '64%', '78%', '55%', '85%', '70%', '60%', '88%', '74%', '66%', '81%', '58%']

/** Placeholder rows with the table's column layout, so content does not jump when data arrives. */
export function LogsSkeleton() {
  return (
    <div className="logs__grid" role="status" aria-label="Carregando logs">
      {WIDTHS.map((width, i) => (
        <div className="skeleton-row" key={i} aria-hidden="true">
          <span className="skeleton" style={{ width: '80%' }} />
          <span className="skeleton" style={{ width: 56, height: 18, borderRadius: 999 }} />
          <span className="skeleton" style={{ width: 32 }} />
          <span className="skeleton" style={{ width: '70%' }} />
          <span className="skeleton" style={{ width: '60%' }} />
          <span className="skeleton" style={{ width }} />
        </div>
      ))}
      <span className="sr-only">Carregando logs…</span>
    </div>
  )
}
