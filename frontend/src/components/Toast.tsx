import React from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { springSnappy } from '../constants/motion'

export interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'info'
  message: string
}

interface ToastProps {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.96 }}
            transition={springSnappy}
            className={`pointer-events-auto flex items-center justify-between gap-3 rounded-lg p-3.5 shadow-editorial-lg border ${
              toast.type === 'success'
                ? 'bg-white border-forest text-ink shadow-editorial'
                : toast.type === 'error'
                ? 'bg-white border-terracotta text-ink shadow-editorial'
                : 'bg-white border-border text-ink shadow-editorial'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {toast.type === 'success' && <CheckCircle2 className="h-4 w-4 text-forest flex-shrink-0" />}
              {toast.type === 'error' && <AlertCircle className="h-4 w-4 text-terracotta flex-shrink-0" />}
              {toast.type === 'info' && <Info className="h-4 w-4 text-forest flex-shrink-0" />}
              <span className="text-xs font-medium leading-snug">{toast.message}</span>
            </div>

            <button
              onClick={() => onDismiss(toast.id)}
              className="rounded-md p-1 text-ink-muted hover:text-ink transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
