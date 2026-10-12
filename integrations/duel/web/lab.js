const $ = id => document.getElementById(id)
const names = { draw: 'Karte gezogen', summon: 'Beschwörung', chain: 'Effekt aktiviert', chain_step: 'Kette wird aufgelöst', attack: 'Angriff', lp: 'Lebenspunkte geändert', move: 'Kartenbewegung', position: 'Position geändert', turn: 'Neuer Zug', phase: 'Phasenwechsel', win: 'Duell beendet' }
const phases = { 1: 'Ziehphase', 2: 'Vorbereitungsphase', 4: 'Hauptphase 1', 8: 'Kampfbeginn', 16: 'Kampfphase', 32: 'Schadensschritt', 64: 'Schadensberechnung', 128: 'Kampfende', 256: 'Hauptphase 2', 512: 'Endphase' }
let socket, state, lastEvent = 0, sent = false, selected = new Set(), animationTimer, previousCard
document.body.dataset.motion = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'reduced' : 'full'
$('motion').value = document.body.dataset.motion
$('motion').onchange = () => { document.body.dataset.motion = $('motion').value }

function text(tag, value, className) { const e = document.createElement(tag); e.textContent = value; if (className) e.className = className; return e }
function card(value, position) {
  if (!value) { const back = text('div', '', 'card-back'); back.setAttribute('aria-label', 'Verdeckte Karte'); return back }
  const button = text('button', '', 'card' + (position & 12 ? ' defense' : ''))
  button.type = 'button'; button.setAttribute('aria-label', `Kartenvorschau: ${value.name}`)
  button.append(text('strong', value.name), text('span', '✦', 'card-mark'), text('small', `${value.atk} ATK · ${value.defense} DEF`))
  button.onclick = () => { previousCard = button; $('card-title').textContent = value.name; $('card-stats').textContent = `${value.atk} ATK · ${value.defense} DEF`; $('card-text').textContent = value.description; $('preview').showModal() }
  return button
}
$('close-preview').onclick = () => $('preview').close()
$('preview').onclose = () => { if (previousCard?.isConnected) previousCard.focus() }
$('surrender').onclick = () => {
  if (sent || !state || state.ended || socket?.readyState !== WebSocket.OPEN) return
  if (!window.confirm('Duell wirklich aufgeben? Dein Gegner gewinnt dieses Testduell.')) return
  sent = true
  $('surrender').disabled = true
  $('actions').querySelectorAll('button').forEach(b => b.disabled = true)
  socket.send(JSON.stringify({ type: 'surrender' }))
}

function answer(indices) {
  if (sent || !state?.prompt || socket?.readyState !== WebSocket.OPEN) return
  sent = true
  $('surrender').disabled = true
  socket.send(JSON.stringify({ type: 'answer', prompt: state.prompt.id, selected: indices }))
  $('actions').querySelectorAll('button').forEach(b => b.disabled = true)
}
function decisions() {
  const p = state.prompt
  $('actions').replaceChildren()
  $('surrender').disabled = state.ended || socket?.readyState !== WebSocket.OPEN
  $('result-reason').textContent = state.end_reason === 'surrender' ? (state.winner === state.seat ? 'Dein Gegner hat aufgegeben.' : 'Du hast aufgegeben.') : ''
  $('decision-title').textContent = state.ended ? (state.winner === state.seat ? 'Du hast gewonnen.' : state.winner === 2 ? 'Unentschieden.' : 'Dein Gegner hat gewonnen.') : p?.title || 'Dein Gegner entscheidet …'
  if (!p) return
  if (p.select) $('actions').append(text('p', `Wähle ${p.minimum} bis ${p.maximum} Karten.`))
  p.choices.forEach((c, index) => {
    const button = text('button', c.label); button.type = 'button'; button.dataset.choice = index
    if (p.select) button.setAttribute('aria-pressed', 'false')
    button.onclick = () => {
      if (!p.select) { answer([index]); return }
      if (selected.has(index)) selected.delete(index); else selected.add(index)
      button.setAttribute('aria-pressed', String(selected.has(index)))
      $('confirm').disabled = selected.size < p.minimum || selected.size > p.maximum
    }
    $('actions').append(button)
  })
  if (p.select) {
    const confirm = text('button', 'Auswahl bestätigen'); confirm.id = 'confirm'; confirm.disabled = p.minimum > 0
    confirm.onclick = () => answer([...selected]); $('actions').append(confirm)
  }
}
function render(message) {
  const first = !state
  state = message; sent = false; selected.clear()
  $('table').dataset.revision = String(state.revision)
  $('table').hidden = false; $('login').hidden = true
  $('connection').textContent = `Verbunden als Labor-Spieler ${state.seat + 1} · EDOPro API 11`
  for (const [prefix, player] of [['own', state.seat], ['opponent', 1 - state.seat]]) {
    const board = state.boards[player]
    $(`${prefix}-lp`).textContent = `${board.lp.toLocaleString('de-DE')} LP`
    $(`${prefix}-deck`).textContent = `${board.deck} im Deck · ${board.grave.length} im Friedhof`
    $(`${prefix}-hand`).replaceChildren(...board.hand.map(c => card(c, 1)))
    const zones = []
    for (const zone of [4, 8]) for (let sequence = 0; sequence < 5; sequence++) {
      const holder = text('div', '', 'zone'), entry = board.field.find(c => c.zone === zone && c.sequence === sequence)
      if (entry) holder.append(card(entry.card, entry.position)); else holder.append(text('span', `${zone === 4 ? 'M' : 'Z/F'} ${sequence + 1}`))
      zones.push(holder)
    }
    $(`${prefix}-field`).replaceChildren(...zones)
  }
  $('phase').textContent = phases[state.phase] || 'Duellbeginn'
  $('turn').textContent = `Zug ${state.turn_number} · ${state.turn === state.seat ? 'Du bist am Zug' : 'Gegner am Zug'}`
  decisions()
  const fresh = state.events.filter(e => e.id > lastEvent)
  lastEvent = Math.max(lastEvent, ...state.events.map(e => e.id))
  $('events').replaceChildren(...state.events.map(e => text('li', `${e.id}. ${names[e.kind] || e.kind}${e.value != null ? `: ${e.value} LP` : ''}`)))
  // D0 presentation: only fresh server events; prompts are never delayed by effects.
  const focus = [...fresh].reverse().find(e => ['win', 'summon', 'chain', 'attack', 'lp', 'draw'].includes(e.kind)) || fresh.at(-1)
  clearTimeout(animationTimer); $('table').className = ''
  if (focus && (!first || state.revision === 1)) {
    $('effect').textContent = names[focus.kind]; void $('table').offsetWidth
    $('table').className = `motion-${focus.kind}`
    animationTimer = setTimeout(() => { $('table').className = '' }, 800)
  }
}
function connect() {
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/duel`)
  socket.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.type === 'state') { $('error').textContent = ''; render(message) }
    else if (message.type === 'waiting') { $('connection').textContent = message.message; $('login').hidden = true }
    else {
      $('error').textContent = message.message; sent = false
      if (state && message.type === 'error') decisions()
      if (message.type === 'failure') {
        $('surrender').disabled = true
        $('actions').querySelectorAll('button').forEach(b => b.disabled = true)
      }
    }
  }
  socket.onclose = () => { $('connection').textContent = 'Verbindung getrennt. Seite neu laden und erneut verbinden.'; $('surrender').disabled = true; $('actions').querySelectorAll('button').forEach(b => b.disabled = true) }
}
$('login').querySelector('form').onsubmit = async event => {
  event.preventDefault()
  try {
    const response = await fetch('/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: $('code').value }) })
    $('code').value = ''
    if (!response.ok) throw new Error('Der Laborzugang ist ungültig.')
    connect()
  } catch (error) { $('error').textContent = error.message }
}
