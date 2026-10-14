import { API_BASE_URL } from '../api/transport'
import type { WorkerPrompt } from './DuelDecisions'

export type GuidedAction = { action:string; card:NonNullable<WorkerPrompt['choices'][number]['card']>; prompt:number; turn:number; afterEvent:number }

export function DuelActionGuide({context,prompt}:{context:GuidedAction;prompt:WorkerPrompt}) {
  const bits=context.card.type || 0
  const title=context.action==='special_summon' ? bits&0x4000000?'Linkbeschwörung':bits&0x800000?'Xyz-Beschwörung':bits&0x2000?'Synchrobeschwörung':bits&0x40?'Fusionsbeschwörung':'Spezialbeschwörung'
    : context.action==='summon'?'Beschwörung': 'Karte setzen'
  const step=prompt.kind==='zones' && prompt.placement ? 'Zielfeld wählen' : prompt.title==='Position wählen'?'Kampfposition wählen':prompt.title
  return <section className="arena-summon-guide" role="status" aria-label="Deine laufende Kartenaktion">
    {context.card.image_url && <img src={API_BASE_URL.replace(/\/api\/?$/,'')+context.card.image_url} alt="" onError={event=>{event.currentTarget.hidden=true}} />}
    <div><small>{title}</small><strong>{context.card.name}</strong><span>{step}{prompt.select && prompt.minimum ? ` · ${prompt.minimum===prompt.maximum?prompt.minimum:`${prompt.minimum}–${prompt.maximum}`} Karte${prompt.maximum===1?'':'n'}`:''}</span>
    {prompt.kind==='zones' && prompt.placement && <p>Klicke auf eines der leuchtenden Felder.</p>}</div>
  </section>
}
