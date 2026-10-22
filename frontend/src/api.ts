import type { BackendHealth, DatasetMetadata, QueryResult } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = ''
    try {
      const data = await res.json()
      errorDetail = data.detail || data.message || JSON.stringify(data)
    } catch {
      errorDetail = await res.text()
    }
    throw new ApiError(
      errorDetail || `Request failed with status ${res.status}`,
      res.status,
      errorDetail
    )
  }
  return res.json()
}

export async function checkBackendHealth(): Promise<BackendHealth> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`, {
      headers: { Accept: 'application/json' },
    })
    const data = await handleResponse<{ status: string; service: string; stage: number }>(res)
    return {
      status: data.status === 'ok' ? 'ok' : 'error',
      service: data.service,
      stage: data.stage,
      message: `${data.service || 'Backend'} online (Stage ${data.stage || 3})`,
    }
  } catch (err: any) {
    return {
      status: 'error',
      message: err.message || 'Cannot reach backend server',
    }
  }
}

export async function fetchDatasets(): Promise<DatasetMetadata[]> {
  const res = await fetch(`${API_BASE_URL}/api/datasets`, {
    headers: { Accept: 'application/json' },
  })
  const json = await handleResponse<{ success: boolean; data: DatasetMetadata[] }>(res)
  return json.data || []
}

export async function fetchDatasetMetadata(datasetId: string): Promise<DatasetMetadata> {
  const res = await fetch(`${API_BASE_URL}/api/datasets/${datasetId}`, {
    headers: { Accept: 'application/json' },
  })
  const json = await handleResponse<{ success: boolean; data: DatasetMetadata }>(res)
  return json.data
}

export async function uploadCSV(file: File): Promise<DatasetMetadata> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE_URL}/api/upload`, {
    method: 'POST',
    body: formData,
  })
  const json = await handleResponse<{ success: boolean; data: DatasetMetadata; message?: string }>(res)
  return json.data
}

export async function executeNaturalLanguageQuery(
  datasetId: string,
  question: string
): Promise<QueryResult> {
  const res = await fetch(`${API_BASE_URL}/api/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      dataset_id: datasetId,
      question: question.trim(),
    }),
  })
  const json = await handleResponse<{
    success: boolean
    dataset_id: string
    question: string
    sql: string
    columns: string[]
    rows: any[][]
    row_count: number
    answer: string
  }>(res)

  return {
    dataset_id: json.dataset_id,
    question: json.question,
    sql: json.sql,
    columns: json.columns,
    rows: json.rows,
    row_count: json.row_count,
    answer: json.answer,
    timestamp: Date.now(),
  }
}
