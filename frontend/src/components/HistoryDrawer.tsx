import React from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X, History, Trash2, ArrowRight } from 'lucide-react'
import type { QueryHistoryItem } from '../types'
import { backdropVariants, drawerVariants } from '../constants/motion'

interface HistoryDrawerProps {
  isOpen: boolean
  history: QueryHistoryItem[]
  onClose: () => void
  onSelectQuery: (item: QueryHistoryItem) => void
  onClearHistory: () => void
}

export const HistoryDrawer: React.FC<HistoryDrawerProps> = ({
  isOpen,
  history,
  onClose,
  onSelectQuery,
  onClearHistory,
}) => {
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
            className="fixed inset-0 bg-[#0B2E22]/30 backdrop-blur-[2px]"
          />

          <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
            <motion.div
              variants={drawerVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="w-screen max-w-md border-l border-border bg-surface p-6 shadow-editorial-lg flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-paper-warm text-ink border border-paper-border">
                    <History className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-serif text-base font-bold text-ink">Inquiry Chronicle</h3>
                    <p className="text-xs text-ink-muted">
                      {history.length} {history.length === 1 ? 'record' : 'records'} logged
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {history.length > 0 && (
                    <button
                      onClick={onClearHistory}
                      className="rounded-sm p-1.5 text-ink-muted hover:text-terracotta"
                      title="Clear history"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={onClose}
                    className="rounded-sm p-1.5 text-ink-muted hover:bg-paper-warm hover:text-ink"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* History list */}
              <div className="mt-4 flex-1 overflow-y-auto space-y-2.5 pr-1">
                {history.length === 0 ? (
                  <div className="py-16 text-center text-xs text-ink-muted space-y-1">
                    <History className="mx-auto h-7 w-7 text-ink-faint mb-2" />
                    <p>No queries recorded in this session.</p>
                    <p className="text-ink-faint">Executed inquiries will be chronicled here.</p>
                  </div>
                ) : (
                  history.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => {
                        onSelectQuery(item)
                        onClose()
                      }}
                      className="cursor-pointer rounded-sm border border-paper-border bg-paper-card p-3 hover:border-forest transition-all shadow-editorial-sm space-y-1.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-semibold text-ink leading-snug">
                          {item.question}
                        </p>
                        <ArrowRight className="h-3.5 w-3.5 text-ink-faint flex-shrink-0 mt-0.5" />
                      </div>

                      <p className="text-[11px] text-ink-secondary line-clamp-2 font-serif">
                        {item.answer}
                      </p>

                      <div className="flex items-center justify-between text-[10px] font-mono text-ink-muted border-t border-paper-border/50 pt-1.5">
                        <span className="text-forest font-semibold">{item.row_count} rows yielded</span>
                        <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>
  )
}
