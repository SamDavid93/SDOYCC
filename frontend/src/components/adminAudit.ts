import { label } from '../i18n'

export const auditActionLabels:Record<string,string>={
  product_settings:'Produktregeln geändert',grant:'Belohnung vergeben',reset_login:'Anmeldung zurücksetzen',
  revoke_sessions:'Alle Sitzungen beenden',block:'Konto sperren',unblock:'Konto entsperren',change_role:'Rolle ändern',
  owner_bootstrap:'Hauptadministrator eingerichtet',special_create:'Sonderkarte angelegt',special_state:'Sonderkartenstatus geändert',
  correction:'Bestand korrigiert',batch_create:'Sammelvergabe angelegt',crafting_rule:'Crafting-Regel geändert',
  crafting_adjustment:'Crafting-Guthaben korrigiert',crafting_settings:'Crafting-Einstellungen geändert',
  season_create:'Saison angelegt',season_publish:'Saison veröffentlicht',season_extend:'Saison verlängert',
  trade_settlement:'Tausch abgeschlossen',trade_moderation:'Handelsmeldung bearbeitet',
  duel_profile_review:'Duellregeln geprüft',duel_restriction:'Duellsperre geändert',duel_admission_policy:'Duellzulassung geändert',
  duel_practice_start:'Testduell gestartet',duel_abort_requested:'Duellabbruch angefordert',duel_recovery_requested:'Duellwiederanlauf geprüft',
}
const names:Record<string,string>={
  rarity_key:'Rarität',currency_key:'CP-Währung',display_name:'Anzeigename',dismantle_value:'Zerlegeertrag',craft_cost:'Herstellungskosten',
  crafting_enabled:'Herstellen aktiv',dismantling_enabled:'Zerlegen aktiv',bulk_enabled:'Sammelzerlegung aktiv',max_quantity:'Aktionslimit',
  version:'Version',sort_order:'Sortierung',id:'Kennung',profile_id:'Regelprofil',engine_approved:'Regelkern freigegeben',
  region_approved:'Region freigegeben',accepting_new:'Neue Duelle zugelassen',restricted_until:'Gesperrt bis',reason:'Begründung',
}
const roles:Record<string,string>={user:'Sammler',support_admin:'Support',admin:'Administrator',super_admin:'Hauptadministrator'}
const states:Record<string,string>={draft:'Entwurf',active:'Aktiv',archived:'Archiviert',published:'Veröffentlicht'}
export function describeAuditState(state:unknown):string {
  if(state==null)return 'Nicht gesetzt'
  if(typeof state==='boolean')return state?'Ja':'Nein'
  if(typeof state!=='object')return states[String(state)]||String(state)
  if(Array.isArray(state))return state.map(describeAuditState).join(', ')
  const value=state as Record<string,unknown>
  if(typeof value.cost==='number')return `${value.name||'Produkt'} · ${value.cost} Punkte · ${value.cards_per_pack||'In Prüfung'} Karten`
  if(typeof value.role==='string'&&typeof value.is_active==='boolean')return `${roles[value.role]||value.role} · ${value.is_active?'Aktiv':'Gesperrt'} · ${value.registered?'Passwort eingerichtet':'Neue Twitch-Bestätigung nötig'} · ${value.active_sessions??0} Sitzungen`
  return Object.entries(value).filter(([key])=>!/password|token|secret|hash|api_key/i.test(key)).map(([key,item])=>
    `${names[key]||key}: ${key==='rarity_key'?label(String(item)):describeAuditState(item)}`).join(' · ')||'Keine Angaben'
}
