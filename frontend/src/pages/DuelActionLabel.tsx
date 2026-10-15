import { Check, CirclePause, EyeOff, RotateCcw, Shield, Sparkles, Swords, X, Zap } from 'lucide-react'

export function duelChoiceAction(action: string | undefined, label: string) {
  if (action) return action
  if (label === 'Ja' || /bestätigen/.test(label)) return 'confirm'
  if (label === 'Nicht anketten') return 'pass'
  if (label === 'Nein' || /abbrechen|Abbrechen/.test(label)) return 'cancel'
  if (/zurücksetzen/.test(label)) return 'reset'
  return undefined
}

export function setActionsLast(a: {action?: string}, b: {action?: string}) {
  const isSet = (action?: string) => action === 'set_monster' || action === 'set_spell'
  return Number(isSet(a.action)) - Number(isSet(b.action))
}

export function DuelActionLabel({action,label}:{action?:string;label:string}) {
  const set=action==='set_monster' || action==='set_spell'
  const summon=action==='summon' || action==='special_summon'
  const resolved = duelChoiceAction(action, label)
  const Icon=set?EyeOff:resolved==='activate'?Zap:resolved==='special_summon'?Sparkles:resolved==='confirm'?Check:resolved==='cancel'?X:resolved==='pass'?CirclePause:resolved==='reset'?RotateCcw:resolved==='position'?Shield:Swords
  const detail=set?'Verdeckt ablegen':action==='activate'?'Effekt ausführen':action==='special_summon'?'Spezialbeschwörung':action==='summon'?'Offen beschwören':resolved==='pass'?'Ohne eigenen Effekt fortfahren':resolved==='cancel'?'Diese Aktion nicht ausführen':''
  return <><span className="duel-action-main">{(set || summon || resolved) && <Icon size={17} aria-hidden="true" />}<span>{label}</span></span>{detail && <small className="duel-action-detail" aria-hidden="true">{detail}</small>}</>
}
