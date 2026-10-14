import type { DuelEvent } from './DuelAnimations'

const soundFor = (event: DuelEvent) => {
  if (event.kind === 'turn') return 'nextturn'
  if (['phase', 'phase_request', 'turn_end'].includes(event.kind)) return 'phase'
  if (event.kind === 'attack') return 'attack'
  if (event.kind === 'position') return 'flip'
  if (event.kind === 'lp') return (event.delta || 0) > 0 ? 'gainlp' : 'damage'
  if (event.kind === 'counter') return event.added ? 'addcounter' : 'removecounter'
  if (event.kind === 'summon') return event.method === 'covered' ? 'set' : event.method === 'flip' ? 'flip' : 'summon'
  if (event.kind === 'move' && event.after && [4, 8].includes(event.after.zone) && (event.after.position || 0) & 10) return 'set'
  return ({ draw: 'draw', shuffle: 'shuffle', lp: 'damage', equip: 'equip', coin: 'coinflip', dice: 'diceroll' } as Record<string, string>)[event.kind]
}

export const bossSoundFor = (event:DuelEvent) => 'boss-'+(({1:'earth',2:'water',4:'fire',8:'wind',16:'light',32:'dark',64:'divine'} as Record<number,string>)[event.card?.attribute || 32] || 'dark')

/** All audio starts after a real user gesture; assets are served by our own site. */
export class DuelSoundPlayer {
  private context: AudioContext | null = null
  private gain: GainNode | null = null
  private buffers = new Map<string, AudioBuffer>()
  private loading = new Set<string>()
  private sources = new Set<AudioScheduledSourceNode>()
  volume = .3

  async unlock() {
    this.context ||= new AudioContext()
    if (!this.gain) { this.gain = this.context.createGain(); this.gain.connect(this.context.destination) }
    this.gain.gain.value = this.volume
    if (this.context.state !== 'running') await this.context.resume()
    for (const name of ['phase', 'nextturn', 'draw', 'attack', 'summon', 'set', 'shuffle', 'flip', 'damage', 'gainlp', 'equip', 'addcounter', 'removecounter', 'coinflip', 'diceroll','boss-dark','boss-light','boss-earth','boss-water','boss-fire','boss-wind','boss-divine']) void this.load(name)
  }

  private async load(name: string) {
    if (!this.context || this.buffers.has(name) || this.loading.has(name)) return
    this.loading.add(name)
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}duel-sounds/${name}.wav`)
      if (!response.ok) return
      const buffer = await this.context.decodeAudioData(await response.arrayBuffer())
      this.buffers.set(name, buffer)
    } catch { /* The synthesized cue remains available if an asset cannot load. */ }
    finally { this.loading.delete(name) }
  }

  setVolume(value: number) {
    this.volume = value
    if (this.gain && this.context) this.gain.gain.setTargetAtTime(value, this.context.currentTime, .02)
  }

  play(event: DuelEvent) {
    if (!this.context || this.context.state !== 'running' || !this.gain) return
    const name = soundFor(event), buffer = name && this.buffers.get(name)
    if (buffer) {
      const source = this.context.createBufferSource()
      source.buffer = buffer; source.connect(this.gain)
      this.sources.add(source); source.onended = () => { this.sources.delete(source); source.disconnect() }
      source.start(); return
    }
    if (name) void this.load(name)
    const pitches = event.kind === 'chain' ? [523, 784, 1047] : event.kind === 'win' ? [523, 659, 784] : event.kind === 'turn_end' ? [659, 523] : event.kind === 'phase_request' ? [440, 554] : event.kind === 'negate' ? [220, 165] : event.kind === 'destroy' || event.kind === 'banish' ? [180, 100] : event.kind === 'phase' || event.kind === 'turn' ? [523, 784] : [440]
    pitches.forEach((frequency, index) => {
      const context = this.context!, oscillator = context.createOscillator(), envelope = context.createGain()
      const at = context.currentTime + index * .09
      oscillator.type = 'sine'; oscillator.frequency.value = frequency
      envelope.gain.setValueAtTime(0, at); envelope.gain.linearRampToValueAtTime(.25, at + .015)
      envelope.gain.exponentialRampToValueAtTime(.001, at + .16)
      oscillator.connect(envelope); envelope.connect(this.gain!)
      this.sources.add(oscillator); oscillator.onended = () => { this.sources.delete(oscillator); oscillator.disconnect(); envelope.disconnect() }
      oscillator.start(at); oscillator.stop(at + .17)
    })
  }

  playBossSummon(event:DuelEvent, seconds=1.65) {
    if(!this.context || this.context.state!=='running' || !this.gain)return
    const name=bossSoundFor(event),buffer=this.buffers.get(name)
    if(!buffer){void this.load(name);this.play(event);return}
    const source=this.context.createBufferSource(),envelope=this.context.createGain(),at=this.context.currentTime
    source.buffer=buffer;source.connect(envelope);envelope.connect(this.gain)
    envelope.gain.setValueAtTime(.8,at)
    envelope.gain.setValueAtTime(.8,at+Math.max(.1,seconds-.25))
    envelope.gain.exponentialRampToValueAtTime(.001,at+seconds)
    this.sources.add(source)
    source.onended=()=>{this.sources.delete(source);source.disconnect();envelope.disconnect()}
    source.start();source.stop(at+Math.min(buffer.duration,seconds))
  }

  playTimerWarning(seconds: number) {
    if (!this.context || this.context.state !== 'running' || !this.gain || this.volume === 0) return
    const pitches = seconds === 60 ? [660, 880] : seconds === 30 ? [880, 880, 1047] : seconds <= 10 ? [1175] : [880]
    pitches.forEach((frequency, index) => {
      const context = this.context!, oscillator = context.createOscillator(), envelope = context.createGain()
      const at = context.currentTime + index * .12
      oscillator.type = 'sine'; oscillator.frequency.value = frequency
      envelope.gain.setValueAtTime(0, at); envelope.gain.linearRampToValueAtTime(.35, at + .01)
      envelope.gain.exponentialRampToValueAtTime(.001, at + .1)
      oscillator.connect(envelope); envelope.connect(this.gain!)
      this.sources.add(oscillator); oscillator.onended = () => { this.sources.delete(oscillator); oscillator.disconnect(); envelope.disconnect() }
      oscillator.start(at); oscillator.stop(at + .11)
    })
  }

  stop() { for (const source of this.sources) { try { source.stop() } catch { /* Already finished. */ } }; this.sources.clear() }
  close() { this.stop(); if (this.context?.state !== 'closed') void this.context?.close() }
}
