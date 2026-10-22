import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  checkBackendHealth,
  fetchDatasets,
  executeNaturalLanguageQuery,
} from './api'
import type {
  BackendHealth,
  DatasetMetadata,
  QueryResult,
  QueryHistoryItem,
} from './types'
import { Header } from './components/Header'
import { HeroScene } from './components/HeroScene'
import { QueryComposer } from './components/QueryComposer'
import { ResultView } from './components/ResultView'
import { DatasetSelector } from './components/DatasetSelector'
import { UploadModal } from './components/UploadModal'
import { DatasetSchemaDrawer } from './components/DatasetSchemaDrawer'
import { HistoryDrawer } from './components/HistoryDrawer'
import { ToastContainer } from './components/Toast'
import type { ToastMessage } from './components/Toast'

export const App: React.FC = () => {
  const [health, setHealth] = useState<BackendHealth>({ status: 'loading' })
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([])
  const [activeDataset, setActiveDataset] = useState<DatasetMetadata | null>(null)
  const [currentResult, setCurrentResult] = useState<QueryResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<QueryHistoryItem[]>([])
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  // Modal / Drawer visibility
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [isDatasetSelectorOpen, setIsDatasetSelectorOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isSchemaOpen, setIsSchemaOpen] = useState(false)

  const workspaceRef = useRef<HTMLDivElement>(null)

  // Toast helper
  const addToast = useCallback((type: 'success' | 'error' | 'info', message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4500)
  }, [])

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  // Load initial backend health and dataset list
  useEffect(() => {
    const initApp = async () => {
      // 1. Health check
      const h = await checkBackendHealth()
      setHealth(h)

      // 2. Load datasets
      try {
        const loadedDatasets = await fetchDatasets()
        setDatasets(loadedDatasets)
        if (loadedDatasets.length > 0) {
          // Prefer 1000_Companies.csv or the first available dataset
          const preferred =
            loadedDatasets.find((d) => d.filename.toLowerCase().includes('companies')) ||
            loadedDatasets[0]
          setActiveDataset(preferred)
        }
      } catch (err: any) {
        console.error('Failed to load datasets:', err)
      }

      // 3. Load history from localStorage
      try {
        const savedHistory = localStorage.getItem('querypilot_editorial_history')
        if (savedHistory) {
          setHistory(JSON.parse(savedHistory))
        }
      } catch (e) {
        console.warn('Could not read localStorage history:', e)
      }
    }

    initApp()
  }, [])

  // Save history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('querypilot_editorial_history', JSON.stringify(history.slice(0, 50)))
    } catch (e) {
      console.warn('Could not save history to localStorage:', e)
    }
  }, [history])

  // Handle Query Submission
  const handleQuerySubmit = async (question: string) => {
    if (!activeDataset) {
      addToast('error', 'Please select or upload a dataset first.')
      setIsDatasetSelectorOpen(true)
      return
    }

    setIsLoading(true)
    setError(null)

    if (workspaceRef.current) {
      workspaceRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }

    try {
      const res = await executeNaturalLanguageQuery(activeDataset.dataset_id, question)
      setCurrentResult(res)

      // Add to query history
      const historyItem: QueryHistoryItem = {
        ...res,
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
        timestamp: Date.now(),
      }
      setHistory((prev) => [historyItem, ...prev])

      addToast('success', `SQL synthesized: ${res.row_count} records returned`)
    } catch (err: any) {
      const errMsg = err.detail || err.message || 'Query failed'
      setError(errMsg)
      addToast('error', errMsg)
    } finally {
      setIsLoading(false)
    }
  }

  // Handle Dataset Switch
  const handleSelectDataset = (dataset: DatasetMetadata) => {
    setActiveDataset(dataset)
    setCurrentResult(null)
    setError(null)
    addToast('info', `Active dataset set to '${dataset.filename}' (${dataset.total_rows.toLocaleString()} rows)`)
  }

  // Handle Upload Success
  const handleUploadSuccess = (newDataset: DatasetMetadata) => {
    setDatasets((prev) => [newDataset, ...prev])
    setActiveDataset(newDataset)
    setCurrentResult(null)
    setError(null)
    addToast('success', `Ingested '${newDataset.filename}' into SQLite sandbox`)
  }

  // Scroll to workspace from Hero
  const scrollToWorkspace = () => {
    workspaceRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col font-sans selection:bg-forest/15 selection:text-forest">
      {/* Editorial Header */}
      <Header
        health={health}
        activeDataset={activeDataset}
        datasetCount={datasets.length}
        historyCount={history.length}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenDatasetSelector={() => setIsDatasetSelectorOpen(true)}
        onOpenHistory={() => setIsHistoryOpen(true)}
        onOpenSchema={() => setIsSchemaOpen(true)}
      />

      {/* Main Focused Question Workspace */}
      <main className="flex-1 pb-20">
        <div ref={workspaceRef} className="mx-auto max-w-3xl sm:max-w-4xl px-4 sm:px-6 lg:px-8 pt-6 sm:pt-10 space-y-8">
          {/* Centered Welcoming Hero */}
          <HeroScene
            activeDataset={activeDataset}
            datasetCount={datasets.length}
            onStartQuerying={scrollToWorkspace}
            onOpenUpload={() => setIsUploadOpen(true)}
            onOpenDatasetSelector={() => setIsDatasetSelectorOpen(true)}
            onOpenSchema={() => setIsSchemaOpen(true)}
          />

          {/* Prominent Question Composer */}
          <QueryComposer
            activeDataset={activeDataset}
            isLoading={isLoading}
            onSubmit={handleQuerySubmit}
            onOpenDatasetSelector={() => setIsDatasetSelectorOpen(true)}
            onOpenUpload={() => setIsUploadOpen(true)}
          />

          {/* Results: SQL, Table, Visualizations */}
          <ResultView
            result={currentResult}
            isLoading={isLoading}
            error={error}
            onRetry={() => {
              if (currentResult?.question) {
                handleQuerySubmit(currentResult.question)
              }
            }}
          />
        </div>
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-border bg-surface/50 py-8 text-center text-xs text-ink-secondary font-mono">
        <div className="mx-auto max-w-4xl px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© {new Date().getFullYear()} QueryPilot AI · Natural Language SQL Analysis.</p>
          <div className="flex items-center gap-3 text-ink-muted">
            <span>FastAPI Backend</span>
            <span>·</span>
            <span>Google Gemini</span>
            <span>·</span>
            <span className="text-forest font-semibold">SQLGlot AST Guard</span>
          </div>
        </div>
      </footer>

      {/* Modals & Slide-over Drawers */}
      <DatasetSelector
        isOpen={isDatasetSelectorOpen}
        datasets={datasets}
        activeDatasetId={activeDataset?.dataset_id || null}
        onClose={() => setIsDatasetSelectorOpen(false)}
        onSelectDataset={handleSelectDataset}
        onOpenUpload={() => setIsUploadOpen(true)}
      />

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />

      <DatasetSchemaDrawer
        isOpen={isSchemaOpen}
        dataset={activeDataset}
        onClose={() => setIsSchemaOpen(false)}
      />

      <HistoryDrawer
        isOpen={isHistoryOpen}
        history={history}
        onClose={() => setIsHistoryOpen(false)}
        onSelectQuery={(item) => {
          setCurrentResult(item)
          if (activeDataset?.dataset_id !== item.dataset_id) {
            const found = datasets.find((d) => d.dataset_id === item.dataset_id)
            if (found) setActiveDataset(found)
          }
          addToast('info', `Loaded inquiry: "${item.question}"`)
        }}
        onClearHistory={() => {
          setHistory([])
          localStorage.removeItem('querypilot_editorial_history')
          addToast('info', 'Chronicle log cleared')
        }}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default App
