import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Loader2, ArrowRight, CornerDownLeft, Sparkles } from 'lucide-react'
import type { DatasetMetadata } from '../types'
import { buttonTapMotion, listItemVariants, staggerListVariants } from '../constants/motion'

interface QueryComposerProps {
  activeDataset: DatasetMetadata | null
  isLoading: boolean
  onSubmit: (question: string) => void
  onOpenDatasetSelector: () => void
  onOpenUpload?: () => void
}

export const QueryComposer: React.FC<QueryComposerProps> = ({
  activeDataset,
  isLoading,
  onSubmit,
  onOpenDatasetSelector,
  onOpenUpload,
}) => {
  const [question, setQuestion] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [question])

  // Context-aware 3 to 4 useful suggested questions
  const getSuggestions = (): string[] => {
    if (!activeDataset) {
      return [
        'How many rows are in this dataset?',
        'Show summary statistics for all numeric columns',
        'Find the top 5 records with highest values',
        'List all unique categories and their counts',
      ]
    }

    const suggestions: string[] = []
    const cols = activeDataset.columns.map((c) => ({
      ...c,
      cleanLower: c.clean_name.toLowerCase(),
    }))

    // 1. Total count query
    suggestions.push(`How many total rows are in ${activeDataset.filename}?`)

    // 2. Metric / grouping query
    const catCol = cols.find((c) =>
      ['state', 'city', 'country', 'region', 'department', 'category', 'genre', 'type', 'industry'].some(
        (k) => c.cleanLower.includes(k)
      )
    )
    const numCol = cols.find((c) => c.sqlite_type === 'REAL' || c.sqlite_type === 'INTEGER')

    if (catCol && numCol) {
      suggestions.push(`What is the average ${numCol.name} grouped by ${catCol.name}?`)
    } else if (numCol) {
      suggestions.push(`What are the top 5 records with highest ${numCol.name}?`)
    } else if (catCol) {
      suggestions.push(`What are the unique values and counts for ${catCol.name}?`)
    }

    // 3. Top records
    const altNumCol = cols.find(
      (c) => (c.sqlite_type === 'REAL' || c.sqlite_type === 'INTEGER') && c.name !== numCol?.name
    )
    if (altNumCol) {
      suggestions.push(`Which records have the highest ${altNumCol.name}?`)
    } else if (numCol && !suggestions.some((s) => s.includes('top 5'))) {
      suggestions.push(`Show the top 5 records with highest ${numCol.name}`)
    } else {
      suggestions.push(`Show the first 10 records from ${activeDataset.table_name}`)
    }

    // 4. Distribution or summary
    if (numCol) {
      suggestions.push(`What is the maximum and minimum ${numCol.name}?`)
    } else {
      suggestions.push(`Show summary statistics for this dataset`)
    }

    // Guarantee exactly 3 or 4 unique suggestions
    const unique = Array.from(new Set(suggestions))
    return unique.slice(0, 4)
  }

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!question.trim() || isLoading) return
    onSubmit(question.trim())
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="w-full">
      {/* Prominent Question Composer Card */}
      <div
        className={`editorial-card rounded-xl p-4 sm:p-6 transition-all duration-200 ease-out ${
          isFocused
            ? 'border-forest ring-2 ring-forest-sage/80 shadow-composer-focus'
            : 'border-border shadow-composer'
        }`}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Natural language question composer textarea */}
          <div className="relative">
            <textarea
              ref={textareaRef}
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              onKeyDown={handleKeyDown}
              placeholder={
                activeDataset
                  ? `Ask any question about ${activeDataset.filename} (e.g. "What are the top 5 records by value?")...`
                  : 'Select a dataset or upload CSV to begin asking questions...'
              }
              className="w-full resize-none bg-transparent font-sans text-base sm:text-lg text-ink placeholder:text-ink-secondary/60 focus:outline-none leading-relaxed transition-colors"
              disabled={isLoading}
            />
          </div>

          {/* Action Footer */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-3 border-t border-border">
            {/* Keyboard shortcut hint / dataset indicator */}
            <div className="flex items-center gap-2 text-xs text-ink-secondary">
              <CornerDownLeft className="h-3.5 w-3.5 text-ink-muted hidden sm:inline" />
              <span className="hidden sm:inline">Press Return to synthesize query · Shift+Return for line break</span>
              {!activeDataset && (
                <div className="flex items-center gap-2">
                  <span className="text-terracotta text-xs font-medium">No dataset selected</span>
                  <button
                    type="button"
                    onClick={onOpenDatasetSelector}
                    className="text-xs font-semibold text-forest underline hover:text-forest-deep"
                  >
                    Choose dataset
                  </button>
                  {onOpenUpload && (
                    <>
                      <span className="text-border">·</span>
                      <button
                        type="button"
                        onClick={onOpenUpload}
                        className="text-xs font-semibold text-forest underline hover:text-forest-deep"
                      >
                        Upload CSV
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Submit button */}
            <motion.button
              {...buttonTapMotion}
              type="submit"
              disabled={!question.trim() || isLoading || !activeDataset}
              className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-xs sm:text-sm font-semibold tracking-wide transition-all shadow-editorial-sm ${
                !question.trim() || isLoading || !activeDataset
                  ? 'bg-forest-sage text-ink-muted cursor-not-allowed border border-border'
                  : 'bg-forest hover:bg-forest-deep text-white cursor-pointer hover:shadow-editorial'
              }`}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                  <span>Synthesizing SQL...</span>
                </>
              ) : (
                <>
                  <span>Ask QueryPilot</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </motion.button>
          </div>
        </form>
      </div>

      {/* Suggested Questions: 3 or 4 useful queries below composer */}
      <AnimatePresence>
        {!isLoading && (
          <motion.div
            variants={staggerListVariants}
            initial="hidden"
            animate="visible"
            className="mt-4 space-y-2"
          >
            <div className="flex items-center gap-1.5 text-xs text-ink-secondary px-1">
              <Sparkles className="h-3.5 w-3.5 text-forest" />
              <span className="font-medium">Suggested inquiries:</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {getSuggestions().map((suggestion, idx) => (
                <motion.button
                  key={idx}
                  variants={listItemVariants}
                  {...buttonTapMotion}
                  type="button"
                  onClick={() => {
                    setQuestion(suggestion)
                    if (activeDataset) {
                      onSubmit(suggestion)
                    }
                  }}
                  className="rounded-lg border border-border bg-surface hover:bg-forest-sage/40 hover:border-forest px-3.5 py-2 text-xs text-ink transition-all shadow-editorial-sm text-left font-medium"
                >
                  {suggestion}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

