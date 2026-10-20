import { useState } from 'react'
import { errorMessage } from '../api/client'
import { useUploadImport } from '../api/queries'
import { ImportList } from '../components/imports/ImportList'
import { ImportProgress } from '../components/imports/ImportProgress'
import { UploadDropzone } from '../components/imports/UploadDropzone'
import { Icon } from '../components/ui/Icon'
import { formatBytes } from '../lib/format'

export function ImportsPage() {
  const upload = useUploadImport()
  const [jobId, setJobId] = useState<number | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)

  const send = (file: File) => {
    setFileName(`${file.name} (${formatBytes(file.size)})`)
    if (file.size === 0) {
      upload.reset()
      setLocalError('O arquivo está vazio. Selecione um arquivo de log com conteúdo.')
      return
    }
    setLocalError(null)
    upload.mutate(file, { onSuccess: (job) => setJobId(job.id) })
  }

  const error = localError ?? (upload.isError ? errorMessage(upload.error) : null)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Importar logs</h1>
          <p>Envie um arquivo; ele é processado em segundo plano e os logs ficam disponíveis para consulta.</p>
        </div>
      </div>

      <div className="imports-grid">
        <section className="card" aria-labelledby="upload-title">
          <div className="card__head">
            <h2 className="card__title" id="upload-title">Novo arquivo</h2>
          </div>
          <div className="card__body job">
            <UploadDropzone onFile={send} disabled={upload.isPending} />
            {upload.isPending && (
              <p role="status" className="card__hint inline-status">
                <span className="spinner" aria-hidden="true" /> Enviando {fileName}…
              </p>
            )}
            {error && (
              <div className="alert alert--error" role="alert">
                <Icon name="alert" />
                <span><strong>Não foi possível importar {fileName}.</strong> {error}</span>
              </div>
            )}
            {jobId != null && !error && !upload.isPending && <ImportProgress jobId={jobId} />}
          </div>
        </section>

        <section className="card" aria-labelledby="recent-title">
          <div className="card__head">
            <h2 className="card__title" id="recent-title">Importações recentes</h2>
            <span className="card__hint">Últimas 50</span>
          </div>
          <div className="card__body card__body--flush">
            <ImportList />
          </div>
        </section>
      </div>
    </>
  )
}
