import React from 'react'
import { motion } from 'motion/react'
import { Database, Plus, History, Code2 } from 'lucide-react'
import type { BackendHealth, DatasetMetadata } from '../types'
import { buttonTapMotion } from '../constants/motion'

interface HeaderProps {
  health: BackendHealth
  activeDataset: DatasetMetadata | null
  datasetCount: number
  historyCount: number
  onOpenUpload: () => void
  onOpenDatasetSelector: () => void
  onOpenHistory: () => void
  onOpenSchema: () => void
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeDataset,
  datasetCount,
  historyCount,
  onOpenUpload,
  onOpenDatasetSelector,
  onOpenHistory,
  onOpenSchema,
}) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand identity: Refined QueryPilot AI Wordmark */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-serif text-xl sm:text-2xl font-bold tracking-tight text-forest-deep">
              QueryPilot
            </span>
            <span className="border-l border-border pl-2 font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
              AI
            </span>
          </div>
          <span className="hidden sm:inline-block rounded-full bg-forest-sage px-2 py-0.5 font-mono text-[10px] font-medium text-forest border border-border">
            FastAPI · SQLite
          </span>
        </div>

        {/* Center: Discreet Dataset Indicator */}
        <div className="hidden md:flex items-center">
          {activeDataset ? (
            <motion.button
              {...buttonTapMotion}
              onClick={onOpenDatasetSelector}
              className="group flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-secondary hover:border-forest transition-colors shadow-editorial-sm"
            >
              <Database className="h-3 w-3 text-forest" />
              <span className="font-medium text-ink max-w-[190px] truncate">
                {activeDataset.filename}
              </span>
              <span className="font-mono text-[11px] text-ink-muted">
                ({activeDataset.total_rows.toLocaleString()} rows)
              </span>
              <span className="font-mono text-[10px] text-forest underline decoration-forest/30 group-hover:decoration-forest">
                Change
              </span>
            </motion.button>
          ) : (
            <motion.button
              {...buttonTapMotion}
              onClick={onOpenDatasetSelector}
              className="flex items-center gap-2 rounded-full border border-dashed border-border px-3 py-1 text-xs text-ink-muted hover:text-forest hover:border-forest"
            >
              <Database className="h-3 w-3" />
              <span>Attach dataset ({datasetCount} in repo)</span>
            </motion.button>
          )}
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          {/* Health indicator */}
          <div
            className="flex items-center gap-1.5 px-2 py-0.5 font-mono text-[11px] text-ink-muted"
            title={health.message}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                health.status === 'ok' ? 'bg-forest' : 'bg-terracotta'
              }`}
            />
            <span className="hidden sm:inline">
              {health.status === 'ok' ? 'Online' : 'Offline'}
            </span>
          </div>

          {/* Schema Inspector */}
          {activeDataset && (
            <motion.button
              {...buttonTapMotion}
              onClick={onOpenSchema}
              className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-medium text-ink-secondary hover:border-forest hover:text-forest shadow-editorial-sm transition-colors"
              title="Inspect Schema"
            >
              <Code2 className="h-3.5 w-3.5 text-forest" />
              <span className="hidden lg:inline">Schema</span>
            </motion.button>
          )}

          {/* Query History */}
          <motion.button
            {...buttonTapMotion}
            onClick={onOpenHistory}
            className="relative flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-medium text-ink-secondary hover:border-forest hover:text-forest shadow-editorial-sm transition-colors"
            title="Query History"
          >
            <History className="h-3.5 w-3.5 text-ink-secondary" />
            <span className="hidden lg:inline">History</span>
            {historyCount > 0 && (
              <span className="flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-forest-sage text-[10px] font-mono font-semibold text-forest border border-border">
                {historyCount}
              </span>
            )}
          </motion.button>

          {/* Upload Button */}
          <motion.button
            {...buttonTapMotion}
            onClick={onOpenUpload}
            className="flex items-center gap-1.5 rounded-lg bg-forest hover:bg-forest-deep px-3 py-1 text-xs font-medium text-white shadow-editorial-sm transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Upload CSV</span>
          </motion.button>
        </div>
      </div>
    </header>
  )
}
