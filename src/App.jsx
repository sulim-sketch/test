import { useState } from 'react'
import SearchBar from './components/SearchBar'
import FinancialTable from './components/FinancialTable'
import { getQuarterlyResults } from './api/supabase'
import './App.css'

export default function App() {
  const [selectedStock, setSelectedStock] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSelect(stock) {
    setSelectedStock(stock)
    setResults(null)
    setError(null)
    setLoading(true)
    try {
      const data = await getQuarterlyResults(stock.ISU_SRT_CD)
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="top-section">
        <h1 className="page-title">분기별 실적 조회</h1>
        <SearchBar onSelect={handleSelect} />
      </div>
      <div className="result-section">
        <FinancialTable
          stock={selectedStock}
          data={results}
          loading={loading}
          error={error}
        />
      </div>
    </div>
  )
}
