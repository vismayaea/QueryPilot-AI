import React, { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X, Code2, Search, Table, Hash, Type, Calendar, ToggleLeft } from 'lucide-react'
import type { DatasetMetadata } from '../types'
import { backdropVariants, drawerVariants } from '../constants/motion'

interface DatasetSchemaDrawerProps {
  isOpen: boolean
  dataset: DatasetMetadata | null
  onClose: () => void
}

export const DatasetSchemaDrawer: React.FC<DatasetSchemaDrawerProps> = ({
  isOpen,
  dataset,
  onClose,
}) => {
  const [search, setSearch] = useState('')

  if (!dataset) return null

  const filteredColumns = dataset.columns.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.clean_name.toLowerCase().includes(search.toLowerCase()) ||
      c.sqlite_type.toLowerCase().includes(search.toLowerCase())
  )

  const getTypeIcon = (sqliteType: string) => {
    switch (sqliteType) {
      case 'INTEGER':
      case 'REAL':
        return <Hash className="h-3.5 w-3.5 text-forest" />
      case 'TEXT':
        return <Type className="h-3.5 w-3.5 text-ink-secondary" />
      case 'DATETIME':
      case 'DATE':
        return <Calendar className="h-3.5 w-3.5 text-terracotta" />
      case 'BOOLEAN':
        return <ToggleLeft className="h-3.5 w-3.5 text-moss" />
      default:
        return <Table className="h-3.5 w-3.5 text-ink-muted" />
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <motion.div
            variants={backdropVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={onClose}
            className="fixed inset-0 bg-[#0B2E22]/25 backdrop-blur-[2px]"
          />

          <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
            <motion.div
              variants={drawerVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="w-screen max-w-md border-l border-border bg-background p-6 shadow-editorial-lg flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-forest-sage text-forest border border-border">
                    <Code2 className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-serif text-base font-bold text-forest-deep">Schema Details</h3>
                    <p className="text-xs text-ink-muted font-mono truncate max-w-[200px]">
                      {dataset.filename}
                    </p>
                  </div>
                </div>

                <button
                  onClick={onClose}
                  className="rounded-lg p-1.5 text-ink-muted hover:bg-forest-sage/40 hover:text-ink transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Dossier Specs */}
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="rounded-sm border border-paper-border bg-paper-card p-3 space-y-0.5">
                  <span className="text-ink-muted uppercase text-[10px]">Table Target</span>
                  <p className="font-semibold text-forest">"{dataset.table_name}"</p>
                </div>
                <div className="rounded-sm border border-paper-border bg-paper-card p-3 space-y-0.5">
                  <span className="text-ink-muted uppercase text-[10px]">Matrix Scope</span>
                  <p className="font-semibold text-ink">
                    {dataset.total_rows.toLocaleString()} × {dataset.total_columns}
                  </p>
                </div>
              </div>

              {/* Search */}
              <div className="relative mt-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-faint" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter columns..."
                  className="w-full rounded-sm border border-paper-border bg-paper-card py-1.5 pl-8 pr-3 text-xs text-ink placeholder-ink-faint focus:outline-none focus:border-forest"
                />
              </div>

              {/* Column list */}
              <div className="mt-4 flex-1 overflow-y-auto space-y-2 pr-1">
                {filteredColumns.map((col, idx) => (
                  <div
                    key={idx}
                    className="rounded-sm border border-paper-border bg-paper-card p-3 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {getTypeIcon(col.sqlite_type)}
                        <span className="font-sans font-semibold text-ink text-xs">{col.name}</span>
                      </div>
                      <span className="rounded-sm bg-forest-light px-1.5 py-0.5 font-mono text-[10px] text-forest font-semibold border border-forest-border/40">
                        {col.sqlite_type}
                      </span>
                    </div>

                    {col.clean_name !== col.name && (
                      <p className="font-mono text-[11px] text-ink-muted">
                        Identifier: <code className="text-ink font-semibold">"{col.clean_name}"</code>
                      </p>
                    )}

                    {col.sample_values && col.sample_values.length > 0 && (
                      <div className="pt-1 border-t border-paper-border/50">
                        <span className="text-[10px] font-mono text-ink-faint uppercase">Recorded Samples:</span>
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {col.sample_values.slice(0, 3).map((val, sIdx) => (
                            <span
                              key={sIdx}
                              className="rounded-sm bg-paper-warm px-1.5 py-0.5 font-mono text-[10px] text-ink-secondary"
                            >
                              {val === null ? 'null' : String(val)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>
  )
}
