import { Flame, Droplets, Wind, Mountain, Sun, Moon, Sparkles, Star, Swords, Shield, Hexagon } from 'lucide-react'
import { API_BASE_URL } from '../api/transport'
import { CardOrigin, TunerBadge } from '../components/CardSymbols'
import type { EngineCard } from './DuelWorkerTable'
import type { DuelLocation } from './DuelDecisions'
import { germanCardText } from './duelGermanText'

const attributes = {1:['ERDE',Mountain],2:['WASSER',Droplets],4:['FEUER',Flame],8:['WIND',Wind],16:['LICHT',Sun],32:['FINSTERNIS',Moon],64:['GÖTTLICH',Sparkles]} as const
const races: Record<number,string> = {1:'Krieger',2:'Hexer',4:'Fee',8:'Unterweltler',16:'Zombie',32:'Maschine',64:'Aqua',128:'Pyro',256:'Fels',512:'Geflügeltes Ungeheuer',1024:'Pflanze',2048:'Insekt',4096:'Donner',8192:'Drache',16384:'Ungeheuer',32768:'Ungeheuer-Krieger',65536:'Dinosaurier',131072:'Fisch',262144:'Seeschlange',524288:'Reptil',1048576:'Psi',2097152:'Göttliches Ungeheuer',4194304:'Schöpfergott',8388608:'Wyrm',16777216:'Cyberse',33554432:'Illusion'}

export function DuelCardInspector({ card, effect, origin, seat, close }: {card:EngineCard|null;effect:string|null;origin:DuelLocation|null;seat:number;close:()=>void}) {
  const type=card?.type || 0, monster=Boolean(type&1), link=Boolean(type&0x4000000), xyz=Boolean(type&0x800000)
  const rating=link ? card?.link ?? card?.level : xyz ? card?.rank ?? card?.level : card?.level
  const attribute=attributes[card?.attribute as keyof typeof attributes]
  const AttributeIcon=attribute?.[1]
  const subtype=monster?null:type&0x10000?'Schnellzauber':type&0x20000?'Permanent':type&0x40000?'Ausrüstung':type&0x80000?'Spielfeld':type&0x100000?'Konter':type&0x80?null:'Normal'
  const kinds=[monster ? races[card?.race || 0] : type&2?'Zauber':'Falle',subtype,type&0x40?'Fusion':null,type&0x2000?'Synchro':null,xyz?'Xyz':null,link?'Link':null,type&0x80?'Ritual':null,type&0x1000000?'Pendel':null,type&0x1000?'Empfänger':null,type&0x20?'Effekt':type&0x10?'Normal':null].filter(Boolean)
  return <aside className={'duel-card-inspector duel-reference-inspector '+(type&2?'is-spell':type&4?'is-trap':'is-monster')} aria-label="Kartenvorschau">
    {card ? <>
      <header className="duel-inspector-heading"><h2>{card.name}</h2><button aria-label="Vorschau schließen" title="Vorschau schließen" onClick={close}>×</button></header>
      <div className="duel-inspector-summary">
        {card.image_url && <img key={card.image_url} src={API_BASE_URL.replace(/\/api\/?$/,'')+card.image_url} alt={card.name} onError={event=>{const image=event.currentTarget;if(card.fallback_image_url && !image.dataset.fallbackAttempted){image.dataset.fallbackAttempted='true';image.src=API_BASE_URL.replace(/\/api\/?$/,'')+card.fallback_image_url}else image.hidden=true}} />}
        <div className="duel-inspector-facts">
          {attribute && AttributeIcon && <span className="duel-card-attribute"><AttributeIcon aria-hidden="true" />{attribute[0]}</span>}
          {!monster && <span className="duel-card-attribute">{type&2?<Sparkles aria-hidden="true" />:<Shield aria-hidden="true" />}{type&2?'ZAUBER':'FALLE'}</span>}
          {monster && rating !== undefined && <span className={'duel-card-rating '+(xyz?'is-rank':link?'is-link':'')} aria-label={`${link?'Link':xyz?'Rang':'Stufe'} ${rating}`}>{link?<Hexagon aria-hidden="true" />:<Star aria-hidden="true" />}<b>{rating}</b><small>{link?'LINK':xyz?'RANG':'STUFE'}</small></span>}
          {monster && <><span className="duel-viewer-stat"><Swords aria-hidden="true" /><b>{card.atk ?? '?'}</b><small>ATK</small></span>{!link && <span className="duel-viewer-stat"><Shield aria-hidden="true" /><b>{card.defense ?? '?'}</b><small>DEF</small></span>}</>}
        </div>
      </div>
      <div className="duel-card-kind">[{kinds.join(' / ') || 'Karte'}]</div>
      <div className="duel-viewer-badges"><TunerBadge type={card.type} />{type&0x1000000 ? <span className="duel-pendulum-scales">Pendel {card.lscale ?? '?'} / {card.rscale ?? '?'}</span>:null}</div>
      {origin && <CardOrigin zone={origin.zone} opponent={origin.owner!==seat} />}
      {effect && <p className="duel-inspector-effect" role="status">{effect}</p>}
      <small>Kartentext</small><p className="duel-card-description">{germanCardText(card)}</p>
    </> : <div className="duel-inspector-empty"><span>◇</span><h2>Kartenvorschau</h2><p>Klicke eine sichtbare Karte an, um Bild und Kartentext hier zu lesen.</p></div>}
  </aside>
}
