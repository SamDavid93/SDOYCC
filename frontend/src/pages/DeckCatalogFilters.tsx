export function DeckCatalogFilters({ scope, group, sort, legality, choose }: {
  scope: string; group: string; sort: string; legality: string;
  choose: (key: 'scope' | 'group' | 'sort' | 'legality', value: string) => void;
}) {
  return <>
    <div className="deck-quick-filters" aria-label="Kartengruppe">{[['all', 'Alle'], ['monster', 'Monster'], ['spell', 'Zauber'], ['trap', 'Fallen'], ['extra', 'Extra-Deck']].map(([value, title]) => <button key={value} aria-pressed={group === value} onClick={() => choose('group', value)}>{title}</button>)}</div>
    <div className="deck-library-selects">
      <label>Kartenauswahl<select value={scope} onChange={e => choose('scope', e.target.value)}><option value="owned">Alle meine Karten</option><option value="available">Meine freien Karten</option><option value="all">Gesamter Katalog</option></select></label>
      <label>Erlaubnis<select aria-label="Erlaubnis" value={legality} onChange={e => choose('legality', e.target.value)}><option value="all">Alle anzeigen</option><option value="allowed">Erlaubte Karten</option><option value="forbidden">Verbotene Karten</option><option value="unverified">Nicht freigegeben</option></select></label>
      <label>Sortieren<select aria-label="Karten sortieren" value={sort} onChange={e => choose('sort', e.target.value)}><option value="name">Name A–Z</option><option value="name_desc">Name Z–A</option><option value="owned">Besitz: viele zuerst</option><option value="atk">Angriff: hoch zuerst</option><option value="level">Stufe / Rang: hoch zuerst</option></select></label>
    </div>
    <p className="deck-simple-help">Grün: hinzufügen möglich · Gelb: Menge ausgeschöpft · Rot: nicht erlaubt. „Frei“ berücksichtigt Karten, die gerade im Handel oder Duell reserviert sind.</p>
  </>
}
