import { useEffect, useRef, useState, type ReactNode } from 'react'
import { API_BASE_URL } from '../api/transport'
import type { EngineCard } from './DuelWorkerTable'
import type { DuelLocation, WorkerPrompt } from './DuelDecisions'

export function DuelPile({ owner, zone, label, values, prompt, disabled, activeLocation, card, chooseAction }: {
  owner:number;zone:number;label:string;values:(EngineCard|null)[];prompt?:WorkerPrompt|null;disabled:boolean;
  activeLocation:DuelLocation|null;chooseAction:(index:number)=>void;
  card:(value:EngineCard|null,key:string,covered?:boolean,location?:DuelLocation)=>ReactNode;
}) {
  const [open,setOpen]=useState(false)
  const ref=useRef<HTMLDetailsElement>(null)
  const [view,setView]=useState<'menu'|'effects'|'cards'>('menu')
  const choices=prompt?.choices.map((choice,index)=>({...choice,index})).filter(choice=>choice.location?.owner===owner && choice.location.zone===zone) || []
  const chain=prompt?.kind==='chain' || prompt?.title==='Auf die Kette reagieren'
  const effects=choices.filter(choice=>!prompt?.select && !prompt?.counter && (choice.action==='activate' || chain && !choice.action && Boolean(choice.card)))
  const summons=choices.filter(choice=>choice.action==='special_summon')
  const actionable=effects.length>0 || summons.length>0
  useEffect(()=>{setOpen(false);setView('menu')},[prompt?.id])
  useEffect(()=>{if(activeLocation?.owner===owner && activeLocation.zone===zone){setOpen(true);setView('cards')}},[activeLocation,owner,zone])
  useEffect(()=>{
    if(!open)return
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);setView('menu');ref.current?.querySelector('summary')?.focus({preventScroll:true})}}
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node && !ref.current?.contains(event.target))setOpen(false)}
    window.addEventListener('keydown',escape)
    window.addEventListener('pointerdown',outside)
    return()=>{window.removeEventListener('keydown',escape);window.removeEventListener('pointerdown',outside)}
  },[open])
  const options=view==='effects'?effects:summons
  return <details ref={ref} open={open} onToggle={event=>setOpen(event.currentTarget.open)} className={'arena-pile'+(!disabled && choices.length?' action-available':'')+(!disabled && effects.length?' effect-available':'')} data-duel-owner={owner} data-duel-zone={zone}>
    <summary onClick={event=>{event.preventDefault();setView('menu');setOpen(!open)}}>{label}{!disabled && actionable && <span className="arena-effect-label">{summons.length?`${summons.length} Beschwörung${summons.length===1?'':'en'}`:'✦ Effekt verfügbar'}</span>}<strong>{values.length}</strong></summary>
    <div className="arena-pile-content arena-pile-browser" role="region" aria-label={`${label}: Aktionen und Karten`}>
      <header><strong>{label}</strong><button aria-label={`${label} schließen`} onClick={()=>setOpen(false)}>×</button></header>
      {view!=='cards' && actionable ? <>
        {view==='menu' && summons.length>0 && <h3>Mögliche Spezialbeschwörungen</h3>}
        {view==='menu' && effects.length>0 && <button className="arena-pile-effect-button" disabled={disabled} onClick={()=>setView('effects')}>✦ Effekt aktivieren ({effects.length})</button>}
        {view==='effects' && <><button className="arena-pile-back" onClick={()=>setView('menu')}>← Zurück</button><h3>Aktivierbare Karten</h3></>}
        <div className="arena-pile-options">{options.map(choice=><button key={choice.index} disabled={disabled} aria-label={choice.label} onClick={()=>{chooseAction(choice.index);setOpen(false)}}>
          {choice.card?.image_url && <img src={API_BASE_URL.replace(/\/api\/?$/,'')+choice.card.image_url} alt="" onError={event=>{event.currentTarget.hidden=true}} />}
          <span><strong>{choice.card?.name || choice.label}</strong><small>{choice.action==='special_summon'?'Spezialbeschwören':choice.label}</small></span><b aria-hidden="true">→</b>
        </button>)}</div>
        <button className="arena-pile-inspect" onClick={()=>setView('cards')}>{label} ansehen · {values.length} Karten</button>
      </> : <>
        {actionable && <button className="arena-pile-back" onClick={()=>setView('menu')}>← Mögliche Aktionen</button>}
        <div className="arena-pile-cards">{values.map((value,index)=>card(value,`${zone}:${index}`,false,prompt?.select || prompt?.counter ? {owner,zone,sequence:index}:undefined))}{!values.length && <small>Leer</small>}</div>
      </>}
    </div>
  </details>
}
