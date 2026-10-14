import { EyeOff, Sparkles, Swords, Zap } from 'lucide-react'

export function DuelActionLabel({action,label}:{action?:string;label:string}) {
  const set=action==='set_monster' || action==='set_spell'
  const summon=action==='summon' || action==='special_summon'
  const Icon=set?EyeOff:action==='activate'?Zap:action==='special_summon'?Sparkles:Swords
  const detail=set?'Verdeckt ablegen':action==='activate'?'Effekt ausführen':action==='special_summon'?'Spezialbeschwörung':action==='summon'?'Offen beschwören':''
  return <><span className="duel-action-main">{(set || summon || action==='activate') && <Icon size={17} aria-hidden="true" />}<span>{label}</span></span>{detail && <small className="duel-action-detail" aria-hidden="true">{detail}</small>}</>
}
