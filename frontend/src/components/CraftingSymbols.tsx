import type { CSSProperties } from 'react'
import './crafting-symbols.css'

// Presentation only: currencies and action permissions always come from the API.
const marks: Record<string, [string, string]> = {
  common: ['C', '#b9c8d5'], rare: ['R', '#77beff'], super_rare: ['SR', '#78e0b0'],
  ultra_rare: ['UR', '#f4d277'], secret_rare: ['ScR', '#d99aff'],
  ultimate_rare: ['UtR', '#f2a96d'], ghost_rare: ['GR', '#d7f7ff'],
  starlight_rare: ['StR', '#f6a7d9'], platinum_secret_rare: ['PSR', '#b8bae9'],
  quarter_century_secret_rare: ['QCSR', '#f1d5a0'], other: ['?', '#9ba5b2'],
}

export function CraftCurrencyIcon({ currency, size=30 }: {currency:string;size?:number}) {
  const rarity=currency.replace(/_cp$/, '')
  const [mark,color]=marks[rarity] || [rarity.split('_').map(s=>s[0]).join('').slice(0,4).toUpperCase(), '#a8c9d6']
  return <span className="craft-currency-icon" style={{'--cp-color':color,width:size,height:size,fontSize:size} as CSSProperties} aria-hidden="true" data-currency={currency}>
    <svg viewBox="0 0 40 40" fill="none"><path d="M20 2 35.6 11v18L20 38 4.4 29V11Z" fill="currentColor" fillOpacity=".13" stroke="currentColor" strokeWidth="1.5"/><path d="m20 5 13 7.5v15L20 35 7 27.5v-15Z" stroke="currentColor" strokeOpacity=".45"/><path d="m10 13 5-3m14 16-5 3" stroke="white" strokeOpacity=".65" strokeLinecap="round"/></svg>
    <b className={mark.length>3?'is-long':mark.length<3?'is-short':''}>{mark}</b>
  </span>
}

export function CraftActionIcon({ kind, size=19 }: {kind:'craft'|'dismantle';size?:number}) {
  return <svg className={`craft-action-icon is-${kind}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind==='craft'?<><path d="m4 20 9-9m-3-4 4-4 7 7-4 4Z"/><path d="M4 3v4M2 5h4m13 11v5m-2.5-2.5h5"/></>:<><path d="M9 3H4v16h5l3-6-4-2 4-5Zm6 1 5-1v7l-5 2 2 4-3 5 6-1v-6"/><path d="m11 1 2 2m8 19 1-2"/></>}
  </svg>
}

export function CraftingIcon({size=19}:{size?:number}) { return <CraftActionIcon kind="craft" size={size}/> }
