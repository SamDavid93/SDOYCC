import { useState } from 'react'
import { CraftActionIcon, CraftCurrencyIcon } from '../components/CraftingSymbols'
import { ErrorBox, useRead, type Page } from '../components/Workflow'
import { label } from '../i18n'
import { PrintingDialog, type Printing } from './CraftingPage'
import './deck-crafting.css'

/** Works on a concrete printing, never on the deck's aggregated card quantity. */
export function DeckCrafting({ cardId, inDeck, revision, changed }: {cardId:number;inDeck:number;revision:number;changed:(message:string)=>void}) {
  const [page,setPage]=useState(1),[printingId,setPrintingId]=useState<number>(),[kind,setKind]=useState<'craft'|'dismantle'>()
  const printings=useRead<Page<Printing>>(`/crafting/cards?card_id=${cardId}&page=${page}&page_size=36`,revision)
  const settings=useRead<{control:{max_quantity:number}}>('/crafting/settings',revision)
  const items=printings.data?.items||[]
  const card=items.find(p=>p.card_printing_id===printingId)
    ||items.find(p=>p.dismantling_enabled&&p.dismantle_available_quantity>0)
    ||items.find(p=>p.quantity>0)
    ||items.find(p=>p.crafting_enabled&&p.currency_balance>=(p.rule?.craft_cost??Infinity))
    ||items.find(p=>p.crafting_enabled)||items[0]
  const canCraft=!!card?.crafting_enabled&&card.currency_balance>=(card.rule?.craft_cost??Infinity)
  const canDismantle=!!card?.dismantling_enabled&&card.dismantle_available_quantity>0
  return <section className="deck-crafting" aria-label="Kartenwerkstatt im Deckeditor">
    <h3><CraftActionIcon kind="craft"/> Kartenwerkstatt</h3>
    <ErrorBox message={printings.error||settings.error}/>
    {!printings.data&&!printings.error?<p role="status">Ausgaben werden geprüft …</p>:!card?<p>Für diese Karte ist keine Druckversion verfügbar.</p>:<>
      <label>Ausgabe / Rarität<select aria-label="Ausgabe / Rarität" value={card.card_printing_id} onChange={e=>setPrintingId(Number(e.target.value))}>{printings.data?.items.map(p=><option key={p.card_printing_id} value={p.card_printing_id}>{label(p.rarity||'Ungeklärt')} · {p.set_code||p.set_name} · Besitz {p.quantity}</option>)}</select></label>
      {printings.data&&printings.data.total>36&&<div className="deck-crafting-pages"><button disabled={page===1} onClick={()=>{setPage(v=>v-1);setPrintingId(undefined)}}>←</button><small>Ausgaben · Seite {page}</small><button disabled={page*36>=printings.data.total} onClick={()=>{setPage(v=>v+1);setPrintingId(undefined)}}>→</button></div>}
      {card.rule&&<div className="deck-crafting-wallet"><CraftCurrencyIcon currency={card.rule.currency_key} size={32}/><span>{card.rule.display_name} CP<strong>{card.currency_balance.toLocaleString('de-DE')} verfügbar</strong></span></div>}
      <div className="deck-crafting-actions">
        <button className="is-craft" disabled={!canCraft||!settings.data} onClick={()=>{setPrintingId(card.card_printing_id);setKind('craft')}}><CraftActionIcon kind="craft"/><span>Herstellen<small>{!card.crafting_enabled?'Nicht herstellbar':canCraft?`${card.rule!.craft_cost} CP`:`${card.rule!.craft_cost} CP · Guthaben fehlt`}</small></span></button>
        <button className="is-dismantle" disabled={!canDismantle||!settings.data} onClick={()=>{setPrintingId(card.card_printing_id);setKind('dismantle')}}><CraftActionIcon kind="dismantle"/><span>Zerlegen<small>{!card.dismantling_enabled?'Nicht zerlegbar':canDismantle?`+${card.rule!.dismantle_value} CP · ${card.dismantle_available_quantity} frei`:'Keine freien Exemplare'}</small></span></button>
      </div>
      <p className="deck-crafting-note">{card.quantity}× diese Ausgabe · {card.dismantle_available_quantity}× zerlegbar{card.effective_protected>0?` · ${card.effective_protected}× geschützt`:''}{card.reserved>0?` · ${card.reserved}× reserviert`:''}</p>
      {inDeck>0&&<p className="deck-crafting-note">Im Deck: {inDeck}× über alle Ausgaben. Zerlegen entfernt keine Deckeinträge; fehlende Exemplare werden danach markiert.</p>}
      {kind&&<PrintingDialog key={`${card.card_printing_id}:${revision}:${kind}`} card={card} kind={kind} maxQuantity={settings.data?.control.max_quantity||1000} close={()=>setKind(undefined)} done={message=>{setKind(undefined);changed(message)}}/>}
    </>}
  </section>
}
