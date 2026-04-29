import './FinancialTable.css'

const ACCOUNTS = [
  { key: 'revenue',          label: '매출액' },
  { key: 'operating_income', label: '영업이익' },
  { key: 'net_income',       label: '당기순이익' },
  { key: 'asset',            label: '자산총계' },
  { key: 'liability',        label: '부채총계' },
  { key: 'equity',           label: '자본총계' },
]

// 단위: 원(KRW)
const SIPMAN   = 100_000             // 십만원
const CHUNMAN  = 10_000_000          // 천만원
const JO       = 1_000_000_000_000  // 1조
const EOK      = 100_000_000        // 1억
const BAEK_EOK = 10_000_000_000     // 100억

function formatValue(raw) {
  const n = Number(raw)
  if (!raw || raw === '' || isNaN(n)) return '-'

  const negative = n < 0
  const abs = Math.abs(n)

  // 1억 미만은 십만원 단위, 이상은 천만원 단위로 반올림
  const unit = abs < EOK ? SIPMAN : CHUNMAN
  const rounded = Math.round(abs / unit) * unit
  if (rounded === 0) return '0'

  let formatted
  if (rounded >= JO) {
    const jo = Math.floor(rounded / JO)
    const eokRem = Math.floor((rounded % JO) / EOK)
    formatted = eokRem > 0 ? `${jo}조 ${eokRem}억` : `${jo}조`
  } else if (rounded >= BAEK_EOK) {
    const eok = Math.round(rounded / EOK)
    formatted = `${eok}억`
  } else if (rounded >= EOK) {
    const eok = Math.floor(rounded / EOK)
    const man = Math.floor((rounded % EOK) / 10_000)
    if (eok > 0 && man > 0) formatted = `${eok}억 ${man.toLocaleString()}만`
    else                     formatted = `${eok}억`
  } else {
    const man = Math.floor(rounded / 10_000)
    formatted = `${man.toLocaleString()}만`
  }

  return negative ? `(${formatted})` : formatted
}

function isNegative(raw) {
  const n = Number(raw)
  return !isNaN(n) && n < 0
}

export default function FinancialTable({ stock, data, mode, year, loading, error }) {
  if (loading) {
    return <div className="ft-status">실적 데이터를 불러오는 중...</div>
  }
  if (error) {
    return <div className="ft-status ft-error">{error}</div>
  }
  if (!data) return null
  if (data.length === 0) {
    return <div className="ft-status">적재된 실적 데이터가 없습니다.</div>
  }

  const isConsolidated = data[0]?.is_consolidated
  const columns = mode === 'annual'
    ? [{ key: year, label: `${year}년`, data: data[0] }]
    : data.map((r) => ({
        key: `${r.bsns_year}-${r.quarter}`,
        label: `${r.bsns_year} ${r.quarter}Q`,
        data: r,
      }))

  return (
    <div className="ft-container">
      <div className="ft-header">
        <span className="ft-title">{stock.ISU_ABBRV}</span>
        <span className="ft-meta">
          {stock.ISU_SRT_CD} · {isConsolidated ? '연결' : '별도'}
        </span>
      </div>
      <div className="ft-scroll">
        <table className="ft-table">
          <thead>
            <tr>
              <th className="ft-label-col">항목</th>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ACCOUNTS.map((acc) => (
              <tr key={acc.key}>
                <td className="ft-label-col">{acc.label}</td>
                {columns.map((c) => {
                  const raw = c.data[acc.key]
                  return (
                    <td
                      key={c.key}
                      className={isNegative(raw) ? 'ft-neg' : ''}
                    >
                      {formatValue(raw)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
