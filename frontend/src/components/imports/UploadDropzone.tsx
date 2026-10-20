import { useRef, useState, type DragEvent } from 'react'
import { Icon } from '../ui/Icon'

interface UploadDropzoneProps {
  onFile: (file: File) => void
  disabled?: boolean
}

/** Drag-and-drop area with a regular file button as the keyboard / touch alternative. */
export function UploadDropzone({ onFile, disabled }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    const file = event.dataTransfer.files[0]
    if (file) onFile(file)
  }

  return (
    <div
      className={`dropzone${dragging ? ' dropzone--active' : ''}`}
      onDragEnter={(event) => { event.preventDefault(); if (!disabled) setDragging(true) }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false)
      }}
      onDrop={onDrop}
    >
      <span className="dropzone__icon"><Icon name="upload" size={32} /></span>
      <p className="dropzone__title">{dragging ? 'Solte o arquivo para importar' : 'Arraste um arquivo de log para cá'}</p>
      <p className="dropzone__hint">ou</p>
      <button type="button" className="btn btn--primary" onClick={() => inputRef.current?.click()} disabled={disabled}>
        <Icon name="file" /> Selecionar arquivo
      </button>
      <p className="dropzone__hint">Arquivos de texto (.log, .txt, .jsonl, .csv). Linhas em texto, JSON ou CSV com cabeçalho.</p>
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        accept=".log,.txt,.json,.jsonl,.ndjson,.csv,text/plain,application/json,text/csv"
        aria-label="Arquivo de log"
        tabIndex={-1}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onFile(file)
          event.target.value = ''
        }}
      />
    </div>
  )
}
