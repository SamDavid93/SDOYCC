import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import type { CardRecord } from '../data/cards'
import { label } from '../i18n'
import { CardVisual } from './CardVisual'

export function OpeningCardPreview({ card, packName, close }: { card: CardRecord; packName: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current!
    const previousFocus = document.activeElement as HTMLElement | null
    element.showModal()
    return () => {
      element.close()
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
    }
  }, [])
  const specifications = [
    ['Typ / Unterart', card.race ? label(card.race) : null],
    ['Attribut', card.attribute ? label(card.attribute) : null],
    ['Stufe / Rang', card.level], ['Angriff', card.atk], ['Verteidigung', card.defense],
    ['Pendelskala', card.scale], ['Linkwert', card.link_value],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '')

  return <dialog ref={dialog} className="opening-card-preview" aria-labelledby="opening-card-title" onCancel={event => { event.preventDefault(); event.stopPropagation(); close() }}>
    <header className="opening-preview-header"><span>KARTENVORSCHAU</span><button type="button" className="opening-secondary" onClick={close} aria-label="Kartenvorschau schließen" autoFocus><X size={20} /></button></header>
    <div className="opening-preview-layout">
      <div className="opening-preview-art"><CardVisual card={card} /></div>
      <section className="opening-preview-details">
        <p className="opening-preview-rarity">{label(card.rarity)}</p>
        <h2 id="opening-card-title">{card.name}</h2>
        <p className="opening-preview-pack">Gezogen aus: <strong>{packName}</strong></p>
        <p>{label(card.type)}</p>
        {!!specifications.length && <dl className="opening-preview-specifications">{specifications.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>}
        <h3>Kartentext</h3>
        {card.description?.trim() && card.description_language === 'en' && <p className="opening-preview-language">Englischer Originaltext · Deutsche Übersetzung nicht verfügbar</p>}
        <p className="opening-preview-description">{card.description?.trim() || 'Für diese Karte liegt noch kein Kartentext vor.'}</p>
      </section>
    </div>
    <footer className="opening-preview-footer"><button type="button" className="opening-primary" onClick={close}>Zurück zu deinen Karten</button></footer>
  </dialog>
}
