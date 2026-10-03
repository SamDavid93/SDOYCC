import { useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink } from 'react-router-dom'
import { CheckCircle2, X } from 'lucide-react'
import { purchaseBooster, type BoosterSummary } from '../api/client'

type Receipt = {
  booster: BoosterSummary
  quantity: number
  spent: number
  balance: number
  owned: number
}

export function usePurchaseFeedback() {
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [purchasingId, setPurchasingId] = useState<number | null>(null)
  const buyPack = async (booster: BoosterSummary) => {
    setReceipt(null)
    setPurchasingId(booster.id)
    try {
      const result = await purchaseBooster(booster.id)
      setReceipt({ booster: { ...booster, owned: result.owned, purchased_total: result.purchased_total, purchases_remaining: result.purchases_remaining }, quantity: result.purchased, spent: result.total_cost, balance: result.credits_remaining, owned: result.owned })
      return result
    } finally {
      setPurchasingId(null)
    }
  }
  return { receipt, purchasingId, buyPack, dismiss: () => setReceipt(null) }
}

export function PurchaseFeedback({ receipt, dismiss, onOpen, busy }: {
  receipt: Receipt | null
  dismiss: () => void
  onOpen?: (booster: BoosterSummary) => void
  busy: boolean
}) {
  if (!receipt) return null
  return createPortal(<aside className="purchase-feedback" aria-label="Kaufbestätigung">
    <button className="icon-button purchase-feedback-close" aria-label="Kaufbestätigung schließen" onClick={dismiss}><X size={18} /></button>
    <div role="status" aria-live="polite" aria-atomic="true">
      <div className="purchase-feedback-title"><CheckCircle2 size={24} aria-hidden="true" /><strong>{receipt.booster.product_type === 'structure_deck' ? 'Structure Deck erfolgreich gekauft!' : 'Booster erfolgreich gekauft!'}</strong></div>
      <p className="purchase-feedback-name">{receipt.quantity} × {receipt.booster.name}</p>
      <dl><div><dt>Bezahlt</dt><dd>{receipt.spent.toLocaleString('de-DE')} Sammelpunkte</dd></div><div><dt>Neuer Kontostand</dt><dd>{receipt.balance.toLocaleString('de-DE')} Sammelpunkte</dd></div><div><dt>Jetzt im Bestand</dt><dd>{receipt.owned} {receipt.owned === 1 ? 'Pack' : 'Packs'}</dd></div></dl>
    </div>
    <div className="purchase-feedback-actions">
      {onOpen
        ? <button className="primary-button" disabled={busy} onClick={() => { dismiss(); onOpen(receipt.booster) }}>Jetzt kostenlos öffnen</button>
        : <NavLink className="primary-button" to={`/boosters/${receipt.booster.id}`} onClick={dismiss}>Zum gekauften Booster</NavLink>}
      <button className="outline-button" onClick={dismiss}>Weiter stöbern</button>
      <NavLink className="receipt-vault-link" to="/my-packs" onClick={dismiss}>In „Meine Packs“ ansehen →</NavLink>
    </div>
  </aside>, document.body)
}
