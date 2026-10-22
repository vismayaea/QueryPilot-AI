export interface ColumnMetadata {
  name: string
  clean_name: string
  original_name: string
  inferred_type: string
  sqlite_type: string
  sample_values?: (string | number | boolean | null)[]
}

export interface DatasetMetadata {
  dataset_id: string
  filename: string
  table_name: string
  total_rows: number
  total_columns: number
  columns: ColumnMetadata[]
  preview_rows: Record<string, any>[]
  created_at: string
}

export interface QueryResult {
  dataset_id: string
  question: string
  sql: string
  columns: string[]
  rows: any[][]
  row_count: number
  answer: string
  timestamp?: number
}

export interface QueryHistoryItem extends QueryResult {
  id: string
  timestamp: number
}

export interface BackendHealth {
  status: 'ok' | 'error' | 'loading'
  service?: string
  stage?: number
  message?: string
}
