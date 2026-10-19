import { useQuery } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { apiGet } from './api/client'
import { DashboardPage } from './pages/DashboardPage'
import { LogsPage } from './pages/LogsPage'

function ApiStatus() {
  const { isError, isPending } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<{ status: string }>('/health'),
    refetchInterval: 30_000,
  })
  const label = isPending ? 'verificando API…' : isError ? 'API indisponível' : 'API online'
  return <span className={`status ${isError ? 'status--down' : 'status--up'}`}>{label}</span>
}

export default function App() {
  return (
    <div className="layout">
      <header className="header">
        <h1>GTLog</h1>
        <nav>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/logs">Logs</NavLink>
        </nav>
        <ApiStatus />
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/logs" element={<LogsPage />} />
        </Routes>
      </main>
    </div>
  )
}
