import { lazy, Suspense } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useImportCompletionWatcher } from './api/queries'
import { AppHeader } from './components/layout/AppHeader'
import { EmptyState } from './components/ui/StateViews'

// Route-level code splitting: Recharts only loads with the dashboard.
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const LogsPage = lazy(() => import('./pages/LogsPage').then((m) => ({ default: m.LogsPage })))
const ImportsPage = lazy(() => import('./pages/ImportsPage').then((m) => ({ default: m.ImportsPage })))

function PageFallback() {
  return (
    <div className="state" role="status">
      <span className="spinner" aria-hidden="true" /> Carregando…
    </div>
  )
}

export default function App() {
  const { pathname } = useLocation()
  useImportCompletionWatcher()
  // The logs page fills the viewport so the virtualized table owns the scroll.
  const fill = pathname === '/logs'

  return (
    <div className="layout">
      <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
      <AppHeader />
      <main id="conteudo" className={`content${fill ? ' content--fill' : ''}`} tabIndex={-1}>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/importar" element={<ImportsPage />} />
            <Route
              path="*"
              element={
                <EmptyState title="Página não encontrada" text="O endereço acessado não existe.">
                  <Link className="btn btn--primary" to="/dashboard">Ir para o dashboard</Link>
                </EmptyState>
              }
            />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
