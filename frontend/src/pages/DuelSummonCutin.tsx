import { useEffect, useState, type CSSProperties } from 'react'
import { API_BASE_URL } from '../api/transport'
import type { DuelEvent } from './DuelAnimations'
import './duel-cutin.css'

export function bossSummon(event: DuelEvent, seat?:number) {
  if(event.kind!=='summon' || event.player===undefined || seat===undefined || event.player===seat || !event.card || event.method==='covered')return false
  if(event.location?.position!==undefined && !(event.location.position&5))return false
  const card=event.card
  return (card.type || 0)&0x4000 ? false : (card.level || 0)>=((card.type || 0)&0x4000000?3:8) || (card.atk || 0)>=2500
}

const themes:Record<string,{accent:string;label:string}>={fusion:{accent:'#d699ff',label:'FUSION'},synchro:{accent:'#a6ffef',label:'SYNCHRO'},xyz:{accent:'#ffe27b',label:'XYZ'},link:{accent:'#6ce3ff',label:'LINK'},ritual:{accent:'#a6b8ff',label:'RITUAL'},pendulum:{accent:'#85ffb8',label:'PENDEL'}}
export function DuelSummonCutin({event,compact,mode}:{event:DuelEvent;compact:boolean;mode:'full'|'fast'|'reduced'}) {
  const [wasCompact,setWasCompact]=useState(compact)
  useEffect(()=>{if(compact)setWasCompact(true)},[compact])
  const card=event.card!
  const theme=themes[event.method || ''] || {accent:'#f4d06d',label:'BOSS-MONSTER'}
  const link=Boolean((card.type || 0)&0x4000000),xyz=Boolean((card.type || 0)&0x800000)
  const level=card.level || 0
  const source=(value:string)=>/^https?:\/\//.test(value)?value:API_BASE_URL.replace(/\/api\/?$/,'')+value
  return <section className={'duel-summon-cutin'+(compact || wasCompact?' is-compact':'')+' cutin-'+mode} role="status" aria-label="Gegnerisches Bossmonster beschworen" data-summon-method={event.method} style={{'--cutin-accent':theme.accent,'--cutin-time':mode==='fast'?'.65s':mode==='reduced'?'.35s':'1.45s'} as CSSProperties}>
    <div className="cutin-veil" /><div className="cutin-rays" /><div className="cutin-ring" /><div className="cutin-shockwave" />
    <div className="cutin-speedlines" />
    <svg className="cutin-lightning" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true"><path d="M100 480 270 340 235 300 390 190 320 170 480 40 M560 560 650 410 605 380 780 230 715 200 920 55 M20 180 160 240 130 275 260 320 M980 470 850 390 890 350 780 280" /></svg>
    <div className="cutin-sparks" aria-hidden="true">{Array.from({length:24},(_,i)=><i key={i} style={{'--angle':`${i*15}deg`,'--reach':`${180+(i%5)*45}px`,'--delay':`${(i%4)*.025}s`} as CSSProperties} />)}</div>
    <div className="cutin-art-shell">
      {card.image_url ? <div className="cutin-art-crop"><img src={source(card.image_url)} alt="" onError={event=>{const image=event.currentTarget;if(card.fallback_image_url && !image.dataset.fallback){image.dataset.fallback='1';image.src=source(card.fallback_image_url)}else image.hidden=true}} /></div> : <div className="cutin-art-placeholder" aria-hidden="true">✦</div>}
      <div className="cutin-art-sheen" />
    </div>
    <div className="cutin-caption"><span>GEGNERISCHE BESCHWÖRUNG · {theme.label}</span><div className="cutin-rating" aria-label={`${link?'Link':xyz?'Rang':'Stufe'} ${level || '?'}`}>
      {level>0 && (link?<b>LINK–{level}</b>:<><span aria-hidden="true">{Array.from({length:Math.min(12,level)},()=>xyz?'✧':'★').join(' ')}</span><b>{xyz?'RANG':'STUFE'} {level}</b></>)}
    </div><h2>{card.name}</h2><p><strong>ATK {card.atk ?? '?'}</strong>{!link && <strong>DEF {card.defense ?? '?'}</strong>}</p></div>
  </section>
}
