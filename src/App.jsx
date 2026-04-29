import { useState } from 'react'
import SearchBar from './components/SearchBar'
import FinancialTable from './components/FinancialTable'
import { getQuarterlyResults, getAnnualResults } from './api/supabase'
import './App.css'

const YEARS = ['2025', '2024', '2023']

export default function App() {
  const [selectedStock, setSelectedStock] = useState(null)
  const [mode, setMode] = useState('quarterly')
  const [year, setYear] = useState('2025')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function fetchResults(stock, m, y) {
    setResults(null)
    setError(null)
    setLoading(true)
    try {
      const data = m === 'annual'
        ? await getAnnualResults(stock.ISU_SRT_CD, y)
        : await getQuarterlyResults(stock.ISU_SRT_CD, y)
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(stock) {
    setSelectedStock(stock)
    fetchResults(stock, mode, year)
  }

  function handleModeChange(m) {
    setMode(m)
    if (selectedStock) fetchResults(selectedStock, m, year)
  }

  function handleYearChange(e) {
    const y = e.target.value
    setYear(y)
    if (selectedStock) fetchResults(selectedStock, mode, y)
  }

  return (
    <div className="page">
      <div className="top-section">
        <h1 className="page-title">실적 조회</h1>
        <div className="controls">
          <div className="mode-toggle">
            <button
              className={`mode-btn${mode === 'quarterly' ? ' active' : ''}`}
              onClick={() => handleModeChange('quarterly')}
            >
              분기별 실적
            </button>
            <button
              className={`mode-btn${mode === 'annual' ? ' active' : ''}`}
              onClick={() => handleModeChange('annual')}
            >
              연간 실적
            </button>
          </div>
          <div className="search-row">
            <SearchBar onSelect={handleSelect} />
            <select className="year-select" value={year} onChange={handleYearChange}>
              {YEARS.map(y => (
                <option key={y} value={y}>{y}년</option>
              ))}
            </select>
          </div>
        </div>
      </div>
      <div className="result-section">
        <FinancialTable
          stock={selectedStock}
          data={results}
          mode={mode}
          year={year}
          loading={loading}
          error={error}
        />
      </div>
    </div>
  )
}
