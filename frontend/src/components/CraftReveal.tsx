import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { Boxes, Check, SkipForward, Volume2, VolumeX } from 'lucide-react'
import { API_BASE_URL } from '../api/transport'
import { label } from '../i18n'
import { CraftActionIcon, CraftCurrencyIcon } from './CraftingSymbols'
import { craftingSoundEnabled, playCraftingSound, prepareCraftingSound, setCraftingSound, stopCraftingSound } from './craftingSound'
import './craft-reveal.css'

export type CraftedCard = {sourceRef:string;printingId:number;name:string;imageUrl:string;rarity:string|null;currencyKey:string;setLabel:string;quantity:number;newQuantity:number}
const eventName='hub-card-crafted-reveal'
export function revealCraftedCard(card:CraftedCard) { window.dispatchEvent(new CustomEvent<CraftedCard>(eventName,{detail:card})) }

/** Kept outside route content: refreshing stock or closing the quote cannot cut off the reveal. */
export function CraftRevealHost() {
  const [card,setCard]=useState<CraftedCard>()
  const seen=useRef(new Set<string>())
  const close=useCallback(()=>setCard(undefined),[])
  useEffect(()=>{
    const receive=(event:Event)=>{
      const next=(event as CustomEvent<CraftedCard>).detail
      if(!next?.sourceRef||seen.current.has(next.sourceRef))return
      seen.current.add(next.sourceRef)
      if(seen.current.size>200)seen.current.delete(seen.current.values().next().value!)
      setCard(next)
    }
    window.addEventListener(eventName,receive)
    return()=>window.removeEventListener(eventName,receive)
  },[])
  return card?createPortal(<CraftReveal key={card.sourceRef} card={card} close={close}/>,document.body):null
}

function CraftReveal({card,close}:{card:CraftedCard;close:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null)
  const [reduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [phase,setPhase]=useState<'forge'|'reveal'|'collected'>(reduced?'collected':'forge')
  const [sound,setSound]=useState(craftingSoundEnabled),[imageFailed,setImageFailed]=useState(false)
  useEffect(()=>{
    const element=dialog.current!,previous=document.activeElement as HTMLElement|null
    const bodyOverflow=document.body.style.overflow,rootOverflow=document.documentElement.style.overflow
    document.body.style.overflow='hidden';document.documentElement.style.overflow='hidden'
    element.showModal()
    element.querySelector<HTMLButtonElement>('[data-skip]')?.focus()
    playCraftingSound(reduced?'collect':'charge')
    const timers=reduced?[]:[
      window.setTimeout(()=>{setPhase('reveal');playCraftingSound('reveal')},1050),
      window.setTimeout(()=>{setPhase('collected');playCraftingSound('collect')},3650),
    ]
    timers.push(window.setTimeout(close,reduced?2000:4700))
    const hidden=()=>{if(document.hidden)close()}
    document.addEventListener('visibilitychange',hidden)
    return()=>{
      timers.forEach(window.clearTimeout);stopCraftingSound();element.close()
      document.body.style.overflow=bodyOverflow;document.documentElement.style.overflow=rootOverflow
      document.removeEventListener('visibilitychange',hidden)
      const target=previous?.isConnected?previous:document.querySelector<HTMLElement>(`[data-printing-id="${card.printingId}"] button, .deck-crafting select`)
      target?.focus({preventScroll:true})
    }
  },[card.printingId,close,reduced])
  const toggleSound=()=>{
    const enabled=!sound;setSound(enabled);setCraftingSound(enabled)
    if(enabled){prepareCraftingSound();playCraftingSound(phase==='forge'?'charge':phase==='reveal'?'reveal':'collect')}
  }
  return <dialog ref={dialog} className="craft-reveal" data-phase={phase} data-reduced={reduced} aria-label="Neue Karte hergestellt" onCancel={event=>{event.preventDefault();close()}}>
    <div className="craft-reveal-shell">
      <header className="craft-reveal-top"><span><CraftActionIcon kind="craft"/> SDOYCC · KARTENWERKSTATT</span><div><button type="button" aria-label={sound?'Crafting-Ton ausschalten':'Crafting-Ton einschalten'} aria-pressed={sound} onClick={toggleSound}>{sound?<Volume2 size={18}/>:<VolumeX size={18}/>}</button><button type="button" data-skip onClick={close}><SkipForward size={16}/> Überspringen</button></div></header>
      <div className="craft-reveal-title"><p aria-live="polite">{phase==='forge'?'Deine Karte entsteht':phase==='reveal'?'Karte erfolgreich hergestellt':'In deine Sammlung aufgenommen'}</p><h2>{card.name}</h2><span>{label(card.rarity||'')} · {card.setLabel}</span></div>
      <div className="craft-reveal-stage" aria-hidden="true">
        <div className="craft-reveal-halo"/><div className="craft-reveal-orbit"/><div className="craft-reveal-orbit second"/>
        <div className="craft-reveal-shards">{Array.from({length:22},(_,i)=><i key={i} style={{'--angle':`${i*137.5}deg`,'--delay':`${i%7*.045}s`,'--distance':`${125+i%5*28}px`} as CSSProperties}/>)}</div>
        <div className="craft-reveal-card"><div className="craft-reveal-card-face">{!imageFailed?<img src={API_BASE_URL.replace(/\/api\/?$/,'')+card.imageUrl} alt="" onError={()=>setImageFailed(true)}/>:<div className="craft-reveal-fallback"><CraftActionIcon kind="craft" size={56}/><strong>{card.name}</strong></div>}<div className="craft-reveal-card-shine"/></div>{card.quantity>1&&<b className="craft-reveal-quantity">×{card.quantity.toLocaleString('de-DE')}</b>}</div>
        <div className="craft-reveal-core"><CraftCurrencyIcon currency={card.currencyKey} size={72}/></div>
      </div>
      <div className="craft-reveal-collection" data-arrived={phase==='collected'}><span className="craft-reveal-collection-icon">{phase==='collected'?<Check size={25}/>:<Boxes size={25}/>}</span><div><strong>{phase==='collected'?`+${card.quantity.toLocaleString('de-DE')} ${card.quantity===1?'Karte':'Karten'}`:'Deine Sammlung'}</strong><small>{phase==='collected'?`Jetzt ${card.newQuantity.toLocaleString('de-DE')}× diese Ausgabe im Besitz`:'Bereit für dein nächstes Deck'}</small></div></div>
      <footer>Deine Sammlung. Deine nächste Strategie.</footer>
    </div>
  </dialog>
}
