import type { Facets, ImportJob, LogCount, LogEntry, LogPage, Stats } from './types'

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

const NETWORK_ERROR = 'Não foi possível conectar à API. Verifique se o servidor está em execução.'

const STATUS_MESSAGES: Record<number, string> = {
  404: 'Recurso não encontrado.',
  413: 'O arquivo excede o tamanho máximo permitido.',
  415: 'Tipo de arquivo não suportado. Envie um log em texto.',
  422: 'Requisição inválida.',
  500: 'Erro interno no servidor. Tente novamente em instantes.',
  503: 'Serviço temporariamente indisponível.',
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Extracts the `detail` message (string, or FastAPI validation list) from an error response. */
async function readDetail(response: Response): Promise<string> {
  const fallback = STATUS_MESSAGES[response.status] ?? `Erro inesperado (HTTP ${response.status}).`
  try {
    const body: unknown = await response.json()
    const detail = (body as { detail?: unknown } | null)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : null))
        .filter(Boolean)
      if (messages.length) return messages.join('; ')
    }
  } catch {
    // Body is not JSON: fall back to a status-based message.
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers: { Accept: 'application/json', ...init?.headers } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, NETWORK_ERROR)
  }
  if (!response.ok) throw new ApiError(response.status, await readDetail(response))
  return (await response.json()) as T
}

function withQuery(path: string, params?: URLSearchParams): string {
  const query = params?.toString()
  return query ? `${path}?${query}` : path
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string }>('/health', { signal }),

  listImports: (signal?: AbortSignal) => request<ImportJob[]>('/imports', { signal }),
  getImport: (id: number, signal?: AbortSignal) => request<ImportJob>(`/imports/${id}`, { signal }),
  uploadImport: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<ImportJob>('/imports', { method: 'POST', body })
  },

  listLogs: (filters: URLSearchParams, cursor: string | null, limit: number, signal?: AbortSignal) => {
    const params = new URLSearchParams(filters)
    params.set('limit', String(limit))
    if (cursor) params.set('cursor', cursor)
    return request<LogPage>(withQuery('/logs', params), { signal })
  },
  countLogs: (filters: URLSearchParams, signal?: AbortSignal) => request<LogCount>(withQuery('/logs/count', filters), { signal }),
  getLog: (id: number, signal?: AbortSignal) => request<LogEntry>(`/logs/${id}`, { signal }),
  getFacets: (signal?: AbortSignal) => request<Facets>('/logs/facets', { signal }),
  getStats: (filters: URLSearchParams, signal?: AbortSignal) => request<Stats>(withQuery('/stats', filters), { signal }),
}

/** Human-readable message for any error thrown by queries/mutations. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error && error.message) return error.message
  return 'Ocorreu um erro inesperado.'
}
