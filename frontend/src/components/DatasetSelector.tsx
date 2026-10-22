import React, { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  Database,
  X,
  Search,
  Plus,
  Check,
  Columns,
  TableProperties,
  ArrowRight,
} from 'lucide-react'
import type { DatasetMetadata } from '../types'
import { backdropVariants, modalVariants, buttonTapMotion } from '../constants/motion'

interface DatasetSelectorProps {
  isOpen: boolean
  datasets: DatasetMetadata[]
  activeDatasetId: string | null
  onClose: () => void
  onSelectDataset: (dataset: DatasetMetadata) => void
  onOpenUpload: () => void
}

export const DatasetSelector: React.FC<DatasetSelectorProps> = ({
  isOpen,
  datasets,
  activeDatasetId,
  onClose,
  onSelectDataset,
  onOpenUpload,
}) => {
  const [search, setSearch] = useState('')

  const filteredDatasets = datasets.filter(
    (d) =>
      d.filename.toLowerCase().includes(search.toLowerCase()) ||
      d.columns.some((c) => c.name.toLowerCase().includes(search.toLowerCase()))
  )

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          {/* Subtle warm backdrop */}
          <motion.div
            variants={backdropVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={onClose}
            className="fixed inset-0 bg-[#0B2E22]/30 backdrop-blur-[2px]"
          />

          {/* Editorial Modal */}
          <motion.div
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="editorial-card relative w-full max-w-2xl rounded-sm p-6 shadow-editorial-lg overflow-hidden bg-surface"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-paper-border">
              <div>
                <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-forest">
                  Archive Repository
                </span>
                <h3 className="font-serif text-xl font-bold text-ink">
                  Select Target Dataset
                </h3>
                <p className="text-xs text-ink-secondary mt-0.5">
                  Designate which isolated SQLite container to execute queries against.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <motion.button
                  {...buttonTapMotion}
                  onClick={() => {
                    onClose()
                    onOpenUpload()
                  }}
                  className="flex items-center gap-1.5 rounded-sm bg-forest hover:bg-forest-deep px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Upload CSV</span>
                </motion.button>

                <button
                  onClick={onClose}
                  className="rounded-sm p-1.5 text-ink-muted hover:bg-paper-warm hover:text-ink"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Search */}
            <div className="relative mt-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-faint" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter archives by filename or column..."
                className="w-full rounded-sm border border-paper-border bg-paper-card py-2 pl-8 pr-4 text-xs text-ink placeholder-ink-faint focus:outline-none focus:border-forest"
              />
            </div>

            {/* Dataset List */}
            <div className="mt-4 max-h-[380px] space-y-2.5 overflow-y-auto pr-1">
              {filteredDatasets.length === 0 ? (
                <div className="py-12 text-center text-xs text-ink-muted">
                  <Database className="mx-auto h-7 w-7 text-ink-faint mb-2" />
                  <p>No matching datasets found.</p>
                  <button
                    onClick={() => {
                      onClose()
                      onOpenUpload()
                    }}
                    className="mt-2 text-forest font-semibold hover:underline"
                  >
                    Upload a new CSV
                  </button>
                </div>
              ) : (
                filteredDatasets.map((dataset) => {
                  const isSelected = dataset.dataset_id === activeDatasetId
                  return (
                    <div
                      key={dataset.dataset_id}
                      onClick={() => {
                        onSelectDataset(dataset)
                        onClose()
                      }}
                      className={`cursor-pointer rounded-sm p-3.5 border transition-all ${
                        isSelected
                          ? 'border-forest bg-forest-sage/50 shadow-editorial-sm'
                          : 'border-paper-border bg-surface hover:border-paper-border-strong hover:bg-paper-warm/40'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-serif font-bold text-ink text-sm">
                              {dataset.filename}
                            </span>
                            {isSelected && (
                              <span className="flex items-center gap-1 rounded-sm bg-forest px-1.5 py-0.5 text-[10px] font-mono text-white font-medium">
                                <Check className="h-3 w-3" />
                                ACTIVE
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-3 text-xs text-ink-muted font-mono">
                            <span className="flex items-center gap-1">
                              <TableProperties className="h-3 w-3 text-ink-faint" />
                              {dataset.total_rows.toLocaleString()} rows
                            </span>
                            <span>·</span>
                            <span className="flex items-center gap-1">
                              <Columns className="h-3 w-3 text-ink-faint" />
                              {dataset.total_columns} columns
                            </span>
                            <span>·</span>
                            <span className="text-ink-secondary">table: "{dataset.table_name}"</span>
                          </div>

                          {/* Column pills */}
                          <div className="mt-2 flex flex-wrap gap-1 pt-1">
                            {dataset.columns.slice(0, 6).map((col, cIdx) => (
                              <span
                                key={cIdx}
                                className="rounded-sm bg-paper-warm px-1.5 py-0.5 font-mono text-[10px] text-ink-secondary border border-paper-border/60"
                              >
                                {col.name}
                              </span>
                            ))}
                            {dataset.columns.length > 6 && (
                              <span className="font-mono text-[10px] text-ink-faint self-center">
                                +{dataset.columns.length - 6} more
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center self-center text-ink-faint hover:text-forest">
                          <ArrowRight className="h-4 w-4" />
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
