import React, { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  UploadCloud,
  X,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Database,
  ArrowRight,
} from 'lucide-react'
import { uploadCSV } from '../api'
import type { DatasetMetadata } from '../types'
import { backdropVariants, modalVariants, buttonTapMotion } from '../constants/motion'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onUploadSuccess: (dataset: DatasetMetadata) => void
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadedDataset, setUploadedDataset] = useState<DatasetMetadata | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (file: File) => {
    setError(null)
    setUploadedDataset(null)
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Only .csv files are supported for tabular ingestion.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File size exceeds the 10 MB limit.')
      return
    }
    setSelectedFile(file)
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    setIsUploading(true)
    setError(null)
    try {
      const data = await uploadCSV(selectedFile)
      setUploadedDataset(data)
      onUploadSuccess(data)
    } catch (err: any) {
      setError(err.message || 'Failed to ingest CSV file.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setError(null)
    setUploadedDataset(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
          <motion.div
            variants={backdropVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            onClick={onClose}
            className="fixed inset-0 bg-[#0B2E22]/30 backdrop-blur-[2px]"
          />

          <motion.div
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="editorial-card relative w-full max-w-lg rounded-sm p-6 shadow-editorial-lg overflow-hidden bg-surface"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <div>
                <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-forest">
                  Data Ingestion Protocol
                </span>
                <h3 className="font-serif text-xl font-bold text-ink">
                  Ingest Tabular Dataset
                </h3>
                <p className="text-xs text-ink-secondary mt-0.5">
                  Validates CSV headers, infers SQLite types, and provisions isolated database.
                </p>
              </div>

              <button
                onClick={onClose}
                className="rounded-sm p-1.5 text-ink-muted hover:bg-paper-warm hover:text-ink"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="mt-5 space-y-4">
              {uploadedDataset ? (
                /* Success Preview */
                <motion.div
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="rounded-sm border-l-4 border-l-forest border-y border-r border-paper-border bg-paper-card p-5 text-left space-y-3"
                >
                  <div className="flex items-center gap-2 text-forest">
                    <CheckCircle2 className="h-5 w-5" />
                    <h4 className="font-serif text-base font-bold text-ink">
                      Dataset Ingested & Verified
                    </h4>
                  </div>
                  <p className="text-xs font-mono text-ink-secondary">
                    {uploadedDataset.filename} · {uploadedDataset.total_rows.toLocaleString()} records · {uploadedDataset.total_columns} columns
                  </p>
                  <div className="rounded-sm bg-paper-warm p-2.5 font-mono text-[11px] text-ink-muted border border-paper-border">
                    <span>Provisioned SQLite database: </span>
                    <span className="text-forest font-semibold">{uploadedDataset.dataset_id.slice(0, 16)}...db</span>
                  </div>

                  <div className="mt-4 flex items-center justify-end gap-3 pt-2">
                    <button
                      onClick={handleReset}
                      className="rounded-sm border border-paper-border bg-paper-warm px-3 py-1.5 text-xs text-ink-secondary hover:text-ink"
                    >
                      Ingest Another
                    </button>
                    <motion.button
                      {...buttonTapMotion}
                      onClick={onClose}
                      className="flex items-center gap-1.5 rounded-sm bg-forest px-4 py-1.5 text-xs font-semibold text-white hover:bg-forest-deep transition-colors"
                    >
                      <span>Open in Workspace</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </motion.button>
                  </div>
                </motion.div>
              ) : (
                /* Dropzone */
                <>
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`cursor-pointer rounded-sm border-2 border-dashed p-8 text-center transition-all ${
                      isDragging
                        ? 'border-forest bg-forest-sage/40'
                        : selectedFile
                        ? 'border-forest/60 bg-surface'
                        : 'border-border bg-paper-warm/50 hover:border-forest/50 hover:bg-surface'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      onChange={handleFileChange}
                      className="hidden"
                    />

                    <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-sm bg-forest-sage text-forest border border-border">
                      {selectedFile ? (
                        <FileText className="h-5 w-5" />
                      ) : (
                        <UploadCloud className="h-5 w-5" />
                      )}
                    </div>

                    <div className="mt-3">
                      {selectedFile ? (
                        <div className="space-y-1">
                          <p className="text-sm font-serif font-bold text-ink">{selectedFile.name}</p>
                          <p className="text-xs font-mono text-ink-muted">
                            {(selectedFile.size / 1024).toFixed(1)} KB · Ready to ingest
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <p className="text-xs font-medium text-ink sm:text-sm">
                            Drop CSV file here, or <span className="text-forest font-semibold underline">browse local directory</span>
                          </p>
                          <p className="text-[11px] text-ink-muted font-mono">
                            Maximum 10 MB · Validates header uniqueness & type structure
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Error display */}
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex items-center gap-2 rounded-sm border border-terracotta/30 bg-terracotta-light p-3 text-xs text-terracotta"
                    >
                      <AlertCircle className="h-4 w-4 flex-shrink-0" />
                      <span className="font-mono">{error}</span>
                    </motion.div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      onClick={onClose}
                      disabled={isUploading}
                      className="rounded-sm px-4 py-2 text-xs font-medium text-ink-muted hover:text-ink"
                    >
                      Cancel
                    </button>

                    <motion.button
                      {...buttonTapMotion}
                      onClick={handleUpload}
                      disabled={!selectedFile || isUploading}
                      className={`flex items-center gap-2 rounded-sm px-4 py-2 text-xs font-semibold text-white transition-colors ${
                        !selectedFile || isUploading
                          ? 'bg-paper-border text-ink-faint cursor-not-allowed'
                          : 'bg-forest hover:bg-forest-deep shadow-editorial-sm'
                      }`}
                    >
                      {isUploading ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Validating & Building SQLite...</span>
                        </>
                      ) : (
                        <>
                          <Database className="h-3.5 w-3.5" />
                          <span>Ingest & Sandbox</span>
                        </>
                      )}
                    </motion.button>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
