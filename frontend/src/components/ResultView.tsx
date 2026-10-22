import React, { useState, useMemo, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  Code,
  Table as TableIcon,
  BarChart3,
  Copy,
  Check,
  ShieldCheck,
  Clock,
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import Prism from 'prismjs'
import 'prismjs/components/prism-sql'
import type { QueryResult } from '../types'
import { buttonTapMotion, springSnappy } from '../constants/motion'

interface ResultViewProps {
  result: QueryResult | null
  isLoading: boolean
  error: string | null
  onRetry?: () => void
}

type TabType = 'visual' | 'table' | 'sql'

// Forest Green & Warm Accent Chart Palette
const EDITORIAL_CHART_COLORS = [
  '#123D2C', // Primary dark green
  '#285B43', // Secondary green
  '#4D6B53', // Sage moss
  '#B44A28', // Terracotta
  '#D97706', // Warm ochre
  '#0B2E22', // Deep forest green
  '#3E725C', // Medium forest
]

export const ResultView: React.FC<ResultViewProps> = ({
  result,
  isLoading,
  error,
  onRetry,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('visual')
  const [copiedSql, setCopiedSql] = useState(false)
  const [copiedAnswer, setCopiedAnswer] = useState(false)
  const [tableSearch, setTableSearch] = useState('')
  const [page, setPage] = useState(1)
  const rowsPerPage = 10

  // Highlight SQL
  useEffect(() => {
    if (result?.sql) {
      Prism.highlightAll()
    }
  }, [result?.sql, activeTab])

  const handleCopySql = () => {
    if (!result?.sql) return
    navigator.clipboard.writeText(result.sql)
    setCopiedSql(true)
    setTimeout(() => setCopiedSql(false), 2000)
  }

  const handleCopyAnswer = () => {
    if (!result?.answer) return
    navigator.clipboard.writeText(result.answer)
    setCopiedAnswer(true)
    setTimeout(() => setCopiedAnswer(false), 2000)
  }

  const handleExportCSV = () => {
    if (!result) return
    const header = result.columns.join(',')
    const rows = result.rows.map((row) =>
      row.map((val) => `"${val !== null ? String(val).replace(/"/g, '""') : ''}"`).join(',')
    )
    const csvContent = 'data:text/csv;charset=utf-8,' + [header, ...rows].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `query_result_${Date.now()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Detect chart suitability
  const chartAnalysis = useMemo(() => {
    if (!result || result.row_count === 0 || result.columns.length === 0) {
      return null
    }

    const { columns, rows } = result

    // Single scalar (e.g. COUNT or SUM)
    if (result.row_count === 1 && columns.length === 1) {
      return {
        type: 'scalar' as const,
        label: columns[0],
        value: rows[0][0],
      }
    }

    const sampleRow = rows[0] || []
    let labelColIdx = -1
    let numColIdx = -1

    columns.forEach((_, idx) => {
      const val = sampleRow[idx]
      if (typeof val === 'number') {
        if (numColIdx === -1) numColIdx = idx
      } else {
        if (labelColIdx === -1) labelColIdx = idx
      }
    })

    if (numColIdx === -1) {
      return null
    }

    const data = rows.slice(0, 30).map((row, index) => {
      const name = labelColIdx !== -1 && row[labelColIdx] != null ? String(row[labelColIdx]) : `Row ${index + 1}`
      const value = typeof row[numColIdx] === 'number' ? row[numColIdx] : Number(row[numColIdx]) || 0
      return {
        name,
        value,
        raw: row,
      }
    })

    const chartType = data.length <= 6 ? ('pie' as const) : data.length > 15 ? ('area' as const) : ('bar' as const)

    return {
      type: chartType,
      labelName: labelColIdx !== -1 ? columns[labelColIdx] : 'Category',
      metricName: columns[numColIdx],
      data,
    }
  }, [result])

  // Filter and paginate table data
  const filteredRows = useMemo(() => {
    if (!result) return []
    if (!tableSearch.trim()) return result.rows
    const q = tableSearch.toLowerCase()
    return result.rows.filter((row) =>
      row.some((val) => val != null && String(val).toLowerCase().includes(q))
    )
  }, [result, tableSearch])

  const totalPages = Math.ceil(filteredRows.length / rowsPerPage) || 1
  const paginatedRows = useMemo(() => {
    const start = (page - 1) * rowsPerPage
    return filteredRows.slice(start, start + rowsPerPage)
  }, [filteredRows, page])

  // Loading state: Editorial Processing Dossier
  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="editorial-card rounded-sm p-8 text-center"
        >
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-sm bg-forest-light text-forest border border-forest-border/40">
            <span className="h-4 w-4 border-2 border-forest border-t-transparent animate-spin rounded-full" />
          </div>

          <h3 className="mt-4 font-serif text-lg font-bold text-ink">
            Synthesizing Dialect-Strict SQL
          </h3>
          <p className="mt-1.5 text-xs text-ink-secondary max-w-md mx-auto leading-relaxed">
            QueryPilot is transmitting the column specification to Gemini, receiving SQLite syntax, and passing the AST through SQLGlot validation.
          </p>

          <div className="mt-5 flex items-center justify-center gap-2 font-mono text-[11px] text-ink-muted">
            <span className="bg-paper-warm px-2 py-0.5 border border-paper-border text-forest font-semibold">
              Dialect Generation
            </span>
            <span>→</span>
            <span className="bg-paper-warm px-2 py-0.5 border border-paper-border">
              SQLGlot Verification
            </span>
            <span>→</span>
            <span className="bg-paper-warm px-2 py-0.5 border border-paper-border">
              Sandbox Run
            </span>
          </div>
        </motion.div>
      </div>
    )
  }

  // Error state: Restrained Warm Terracotta Notice
  if (error) {
    return (
      <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-sm border-l-4 border-terracotta border-y border-r border-paper-border bg-paper-card p-5 shadow-editorial-sm"
        >
          <div className="flex items-start gap-3.5">
            <AlertTriangle className="h-5 w-5 text-terracotta flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-serif text-base font-bold text-terracotta">
                Query Security or Syntactic Exception
              </h3>
              <p className="mt-1 text-xs text-ink-secondary font-mono leading-relaxed whitespace-pre-wrap bg-paper-warm p-3 border border-paper-border rounded-sm mt-2">
                {error}
              </p>
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="mt-3.5 rounded-sm bg-terracotta text-white px-3 py-1 text-xs font-semibold hover:bg-terracotta-dark transition-colors"
                >
                  Retry Inquiry
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    )
  }

  if (!result) return null

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={springSnappy}
        className="space-y-4"
      >
        {/* Authoritative Editorial Answer Callout */}
        <div className="editorial-card rounded-sm p-6 border-l-4 border-l-forest">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-forest bg-forest-light px-2 py-0.5 border border-forest-border/40">
                  Analytical Finding
                </span>
                <span className="font-mono text-xs text-ink-muted">
                  {result.row_count} {result.row_count === 1 ? 'row' : 'rows'} yielded
                </span>
              </div>
              <h2 className="font-serif text-2xl sm:text-3xl font-bold text-ink leading-snug tracking-tight">
                {result.answer}
              </h2>
            </div>

            <motion.button
              {...buttonTapMotion}
              onClick={handleCopyAnswer}
              className="flex items-center gap-1.5 rounded-sm border border-paper-border bg-paper-warm px-2.5 py-1 text-xs text-ink-secondary hover:text-ink hover:border-paper-border-strong transition-colors"
              title="Copy statement"
            >
              {copiedAnswer ? <Check className="h-3.5 w-3.5 text-forest" /> : <Copy className="h-3.5 w-3.5" />}
              <span className="hidden sm:inline font-mono text-[11px]">{copiedAnswer ? 'Copied' : 'Copy'}</span>
            </motion.button>
          </div>
        </div>

        {/* Tab Navigation: Architectural Ruled Bar */}
        <div className="flex items-center justify-between border-b border-paper-border pt-1">
          <div className="flex items-center gap-6">
            <button
              onClick={() => setActiveTab('visual')}
              className={`relative pb-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide transition-colors ${
                activeTab === 'visual' ? 'text-forest font-bold' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5" />
              <span>Visual Chart</span>
              {activeTab === 'visual' && (
                <motion.div
                  layoutId="editorial-active-tab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-forest"
                  transition={{ duration: 0.2 }}
                />
              )}
            </button>

            <button
              onClick={() => setActiveTab('table')}
              className={`relative pb-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide transition-colors ${
                activeTab === 'table' ? 'text-forest font-bold' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <TableIcon className="h-3.5 w-3.5" />
              <span>Data Records ({result.row_count})</span>
              {activeTab === 'table' && (
                <motion.div
                  layoutId="editorial-active-tab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-forest"
                  transition={{ duration: 0.2 }}
                />
              )}
            </button>

            <button
              onClick={() => setActiveTab('sql')}
              className={`relative pb-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide transition-colors ${
                activeTab === 'sql' ? 'text-forest font-bold' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Code className="h-3.5 w-3.5" />
              <span>SQL Inspector</span>
              {activeTab === 'sql' && (
                <motion.div
                  layoutId="editorial-active-tab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-forest"
                  transition={{ duration: 0.2 }}
                />
              )}
            </button>
          </div>

          {activeTab === 'table' && result.row_count > 0 && (
            <button
              onClick={handleExportCSV}
              className="flex items-center gap-1 text-xs font-mono text-ink-secondary hover:text-forest pb-2"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Export CSV</span>
            </button>
          )}
        </div>

        {/* Tab Content Panes */}
        <AnimatePresence mode="wait">
          {activeTab === 'visual' && (
            <motion.div
              key="visual-tab"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="editorial-card rounded-sm p-6"
            >
              {chartAnalysis?.type === 'scalar' ? (
                /* Editorial KPI Metric Plate */
                <div className="py-8 text-center space-y-2">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">
                    {chartAnalysis.label}
                  </span>
                  <div className="font-serif text-5xl sm:text-6xl font-bold text-ink tracking-tight">
                    {typeof chartAnalysis.value === 'number'
                      ? chartAnalysis.value.toLocaleString()
                      : String(chartAnalysis.value)}
                  </div>
                  <div className="pt-2 flex items-center justify-center gap-1.5 font-mono text-xs text-forest">
                    <TrendingUp className="h-3.5 w-3.5" />
                    <span>Exact SQLite Computation</span>
                  </div>
                </div>
              ) : chartAnalysis ? (
                /* Recharts Editorial Chart */
                <div className="space-y-4">
                  <div className="flex items-center justify-between font-mono text-xs text-ink-secondary border-b border-paper-border pb-2.5">
                    <div>
                      <span>Metric: </span>
                      <span className="text-forest font-bold">{chartAnalysis.metricName}</span>
                      <span className="mx-2">·</span>
                      <span>Categorized by: </span>
                      <span className="text-ink font-semibold">{chartAnalysis.labelName}</span>
                    </div>
                  </div>

                  <div className="h-72 w-full pt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      {chartAnalysis.type === 'pie' ? (
                        <PieChart>
                          <Pie
                            data={chartAnalysis.data}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={95}
                            innerRadius={45}
                            stroke="#FFFFFF"
                            strokeWidth={2}
                          >
                            {chartAnalysis.data.map((_, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={EDITORIAL_CHART_COLORS[index % EDITORIAL_CHART_COLORS.length]}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#FFFFFF',
                              borderColor: '#E0E5DD',
                              borderRadius: '8px',
                              color: '#17251D',
                              fontSize: '11px',
                              fontFamily: 'JetBrains Mono',
                              boxShadow: '0 4px 12px rgba(18, 61, 44, 0.08)',
                            }}
                          />
                        </PieChart>
                      ) : chartAnalysis.type === 'area' ? (
                        <AreaChart data={chartAnalysis.data} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                          <defs>
                            <linearGradient id="areaEditorialGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#123D2C" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#123D2C" stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#E0E5DD" />
                          <XAxis
                            dataKey="name"
                            stroke="#6C776E"
                            fontSize={11}
                            tickLine={false}
                            angle={-25}
                            textAnchor="end"
                          />
                          <YAxis stroke="#6C776E" fontSize={11} tickLine={false} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#FFFFFF',
                              borderColor: '#E0E5DD',
                              borderRadius: '8px',
                              color: '#17251D',
                              fontSize: '11px',
                              fontFamily: 'JetBrains Mono',
                              boxShadow: '0 4px 12px rgba(18, 61, 44, 0.08)',
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="value"
                            stroke="#123D2C"
                            strokeWidth={2}
                            fillOpacity={1}
                            fill="url(#areaEditorialGradient)"
                          />
                        </AreaChart>
                      ) : (
                        <BarChart data={chartAnalysis.data} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#E0E5DD" />
                          <XAxis
                            dataKey="name"
                            stroke="#6C776E"
                            fontSize={11}
                            tickLine={false}
                            angle={-25}
                            textAnchor="end"
                          />
                          <YAxis stroke="#6C776E" fontSize={11} tickLine={false} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#FFFFFF',
                              borderColor: '#E0E5DD',
                              borderRadius: '8px',
                              color: '#17251D',
                              fontSize: '11px',
                              fontFamily: 'JetBrains Mono',
                              boxShadow: '0 4px 12px rgba(18, 61, 44, 0.08)',
                            }}
                          />
                          <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                            {chartAnalysis.data.map((_, index) => (
                              <Cell
                                key={`bar-${index}`}
                                fill={EDITORIAL_CHART_COLORS[index % EDITORIAL_CHART_COLORS.length]}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      )}
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="py-10 text-center text-xs text-ink-muted">
                  <BarChart3 className="mx-auto h-7 w-7 text-ink-faint mb-2" />
                  <p>No numeric metrics found in this result set for visual graphing.</p>
                  <p className="mt-1 text-ink-faint">Inspect the "Data Records" tab to review row values.</p>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'table' && (
            <motion.div
              key="table-tab"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="editorial-card rounded-sm p-5 space-y-3"
            >
              {/* Search */}
              <div className="flex items-center justify-between gap-4">
                <div className="relative flex-1 max-w-xs">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-faint" />
                  <input
                    type="text"
                    value={tableSearch}
                    onChange={(e) => {
                      setTableSearch(e.target.value)
                      setPage(1)
                    }}
                    placeholder="Search records..."
                    className="w-full rounded-sm border border-paper-border bg-paper-warm/40 py-1 pl-8 pr-3 text-xs text-ink placeholder-ink-faint focus:outline-none focus:border-forest"
                  />
                </div>
                <span className="text-[11px] font-mono text-ink-muted">
                  Displaying {paginatedRows.length} of {filteredRows.length} records
                </span>
              </div>

              {/* Polished Editorial Table */}
              <div className="overflow-x-auto rounded-sm border border-paper-border bg-paper-card">
                <table className="w-full text-left text-xs">
                  <thead className="bg-paper-warm border-b border-paper-border text-[11px] font-mono uppercase tracking-wider text-ink-secondary">
                    <tr>
                      <th className="py-2 px-3 w-10 text-center text-ink-faint">#</th>
                      {result.columns.map((col, idx) => (
                        <th key={idx} className="py-2 px-3 font-semibold text-ink">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-paper-border/60 font-sans">
                    {paginatedRows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-paper-warm/40 transition-colors">
                        <td className="py-2 px-3 text-center font-mono text-ink-faint text-[10px]">
                          {(page - 1) * rowsPerPage + rIdx + 1}
                        </td>
                        {row.map((val, cIdx) => (
                          <td key={cIdx} className="py-2 px-3 text-ink-secondary whitespace-nowrap">
                            {val === null ? (
                              <span className="font-mono text-ink-faint italic">NULL</span>
                            ) : typeof val === 'number' ? (
                              <span className="font-mono text-forest font-semibold">{val.toLocaleString()}</span>
                            ) : (
                              String(val)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-2 text-xs text-ink-muted font-mono">
                  <span>
                    Page {page} of {totalPages}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setPage((p) => Math.max(p - 1, 1))}
                      disabled={page === 1}
                      className="rounded-sm border border-paper-border p-1 hover:bg-paper-warm disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                      disabled={page === totalPages}
                      className="rounded-sm border border-paper-border p-1 hover:bg-paper-warm disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'sql' && (
            <motion.div
              key="sql-tab"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="editorial-card rounded-sm p-6 space-y-4"
            >
              {/* Security verification header */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-paper-border pb-3">
                <div className="flex items-center gap-2 font-mono text-[11px]">
                  <ShieldCheck className="h-4 w-4 text-forest" />
                  <span className="font-semibold text-ink">SQLGlot AST Security Verified</span>
                  <span className="rounded-sm bg-forest-light px-1.5 py-0.5 text-forest border border-forest-border/40 font-semibold">
                    READ-ONLY SELECT
                  </span>
                  <span className="rounded-sm bg-paper-warm px-1.5 py-0.5 text-ink-muted border border-paper-border">
                    LIMIT 100
                  </span>
                </div>

                <motion.button
                  {...buttonTapMotion}
                  onClick={handleCopySql}
                  className="flex items-center gap-1.5 rounded-sm border border-paper-border bg-paper-warm px-2.5 py-1 text-xs text-ink hover:text-forest transition-colors"
                >
                  {copiedSql ? <Check className="h-3.5 w-3.5 text-forest" /> : <Copy className="h-3.5 w-3.5" />}
                  <span className="font-mono text-[11px]">{copiedSql ? 'Copied' : 'Copy SQL'}</span>
                </motion.button>
              </div>

              {/* Syntax highlighted code block on light cream background */}
              <div className="rounded-sm border border-paper-border bg-paper-warm/50 p-4 overflow-x-auto">
                <pre className="language-sql text-xs font-mono">
                  <code>{result.sql}</code>
                </pre>
              </div>

              <div className="flex items-center gap-1.5 text-[11px] font-mono text-ink-muted">
                <Clock className="h-3 w-3" />
                <span>Isolated SQLite execution with strict 5.0s ceiling.</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
