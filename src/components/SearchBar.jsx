import { useState, useEffect, useRef } from 'react'
import { searchStocks } from '../api/supabase'
import './SearchBar.css'

export default function SearchBar({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef(null)
  const containerRef = useRef(null)

  useEffect(() => {
    clearTimeout(debounceRef.current)
    if (!query.trim()) {
      setResults([])
      setOpen(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const data = await searchStocks(query)
        setResults(data)
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
  }, [query])

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleSelect(stock) {
    setQuery(stock.ISU_ABBRV)
    setOpen(false)
    onSelect(stock)
  }

  return (
    <div className="search-wrapper" ref={containerRef}>
      <div className="search-input-row">
        <input
          className="search-input"
          type="text"
          placeholder="종목명을 입력하세요 (예: 삼성전자)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && <span className="search-spinner" />}
      </div>
      {open && results.length > 0 && (
        <ul className="search-dropdown">
          {results.map((s) => (
            <li key={s.ISU_SRT_CD} onClick={() => handleSelect(s)}>
              <span className="stock-name">{s.ISU_ABBRV}</span>
              <span className="stock-code">{s.ISU_SRT_CD}</span>
            </li>
          ))}
        </ul>
      )}
      {open && !loading && results.length === 0 && (
        <div className="search-empty">검색 결과가 없습니다</div>
      )}
    </div>
  )
}
