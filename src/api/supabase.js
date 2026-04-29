const BASE_URL = import.meta.env.VITE_SUPABASE_URL.replace(/\/$/, '')
const API_KEY = import.meta.env.VITE_SUPABASE_KEY

const headers = {
  apikey: API_KEY,
  Authorization: `Bearer ${API_KEY}`,
}

export async function searchStocks(query) {
  if (!query.trim()) return []
  const url = new URL(`${BASE_URL}/listed_stocks`)
  url.searchParams.set('select', 'ISU_ABBRV,ISU_SRT_CD,ISU_NM')
  url.searchParams.set('ISU_ABBRV', `ilike.*${query}*`)
  url.searchParams.set('ISU_NM', 'not.ilike.*우선주*')
  url.searchParams.set('limit', '20')
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error('검색 실패')
  return res.json()
}

export async function getQuarterlyResults(stockCode, year) {
  const url = new URL(`${BASE_URL}/quarterly_results`)
  url.searchParams.set('stock_code', `eq.${stockCode}`)
  url.searchParams.set('bsns_year', `eq.${year}`)
  url.searchParams.set('order', 'quarter.asc')
  url.searchParams.set('select', 'bsns_year,quarter,revenue,operating_income,net_income,asset,liability,equity,is_consolidated')
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error('실적 조회 실패')
  return res.json()
}

export async function getAnnualResults(stockCode, year) {
  const url = new URL(`${BASE_URL}/annual_results`)
  url.searchParams.set('stock_code', `eq.${stockCode}`)
  url.searchParams.set('bsns_year', `eq.${year}`)
  url.searchParams.set('select', 'bsns_year,revenue,operating_income,net_income,asset,liability,equity,is_consolidated')
  const res = await fetch(url, { headers })
  if (!res.ok) throw new Error('실적 조회 실패')
  return res.json()
}
