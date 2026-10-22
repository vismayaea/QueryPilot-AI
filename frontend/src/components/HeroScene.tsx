import React from 'react'
import { motion } from 'motion/react'
import { Database, UploadCloud, Sparkles } from 'lucide-react'
import type { DatasetMetadata } from '../types'
import { heroContainerVariants, heroItemVariants, buttonTapMotion } from '../constants/motion'

interface HeroSceneProps {
  activeDataset: DatasetMetadata | null
  datasetCount: number
  onStartQuerying?: () => void
  onOpenUpload: () => void
  onOpenDatasetSelector: () => void
  onOpenSchema?: () => void
}

export const HeroScene: React.FC<HeroSceneProps> = ({
  activeDataset,
  onOpenUpload,
  onOpenDatasetSelector,
  onOpenSchema,
}) => {
  return (
    <section className="relative pt-4 sm:pt-6 pb-2">
      <motion.div
        variants={heroContainerVariants}
        initial="hidden"
        animate="visible"
        className="w-full text-center space-y-4"
      >
        {/* Refined QueryPilot AI Wordmark */}
        <motion.div variants={heroItemVariants} className="flex justify-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-forest-sage/70 border border-border text-xs font-mono text-forest">
            <Sparkles className="h-3.5 w-3.5 text-forest" />
            <span className="font-semibold tracking-wide">QueryPilot AI</span>
            <span className="text-ink-secondary">·</span>
            <span className="text-ink-secondary">Natural Language SQL</span>
          </div>
        </motion.div>

        {/* Concise Headline */}
        <motion.h1
          variants={heroItemVariants}
          className="font-serif text-3xl sm:text-5xl lg:text-[3.25rem] font-bold text-forest-deep tracking-tight leading-[1.14]"
        >
          What would you like to discover?
        </motion.h1>

        {/* Short Supporting Sentence */}
        <motion.p
          variants={heroItemVariants}
          className="text-base sm:text-lg text-ink-secondary font-sans leading-relaxed max-w-2xl mx-auto"
        >
          Ask questions in plain English to query, analyze, and visualize your data.
          QueryPilot synthesizes verified, read-only SQL in an isolated sandbox.
        </motion.p>

        {/* Compact Controls & Selected-Dataset Indicator */}
        <motion.div
          variants={heroItemVariants}
          className="pt-1 flex flex-wrap items-center justify-center gap-2.5"
        >
          {activeDataset ? (
            /* Clear selected-dataset indicator: shown only when a dataset is selected */
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-1.5 text-xs text-ink shadow-editorial-sm transition-all">
              <span className="h-2 w-2 rounded-full bg-forest animate-pulse" />
              <Database className="h-3.5 w-3.5 text-forest" />
              <span className="text-ink-secondary">Dataset:</span>
              <span className="font-semibold text-forest max-w-[220px] truncate">
                {activeDataset.filename}
              </span>
              <span className="font-mono text-[11px] text-ink-muted">
                ({activeDataset.total_rows.toLocaleString()} rows)
              </span>
              <button
                type="button"
                onClick={onOpenDatasetSelector}
                className="ml-1 text-[11px] font-medium text-forest hover:text-forest-deep underline decoration-forest/30 hover:decoration-forest transition-colors"
                title="Switch active dataset"
              >
                Change
              </button>
              {onOpenSchema && (
                <>
                  <span className="text-border">·</span>
                  <button
                    type="button"
                    onClick={onOpenSchema}
                    className="text-[11px] font-medium text-ink-secondary hover:text-forest transition-colors"
                    title="View dataset schema and columns"
                  >
                    Schema
                  </button>
                </>
              )}
            </div>
          ) : (
            /* Compact dataset selection when none is selected */
            <motion.button
              {...buttonTapMotion}
              onClick={onOpenDatasetSelector}
              className="inline-flex items-center gap-2 rounded-full border border-dashed border-border-strong bg-surface px-4 py-1.5 text-xs font-medium text-ink hover:border-forest hover:text-forest shadow-editorial-sm transition-colors"
            >
              <Database className="h-3.5 w-3.5 text-forest" />
              <span>Select a Dataset</span>
            </motion.button>
          )}

          {/* Compact CSV upload control */}
          <motion.button
            {...buttonTapMotion}
            onClick={onOpenUpload}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3.5 py-1.5 text-xs font-medium text-ink-secondary hover:border-forest hover:text-forest shadow-editorial-sm transition-colors"
          >
            <UploadCloud className="h-3.5 w-3.5 text-forest" />
            <span>Upload CSV</span>
          </motion.button>
        </motion.div>
      </motion.div>
    </section>
  )
}

