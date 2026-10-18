// Original Web Audio cues. Unlock silently in the confirmation click; play only
// after the server has committed the craft. No extra downloads are needed.
let context: AudioContext | undefined
const voices=new Set<OscillatorNode>()
export function craftingSoundEnabled() {
  try { return localStorage.getItem('crafting-sound')!=='off' } catch { return true }
}
export function setCraftingSound(enabled:boolean) {
  try { localStorage.setItem('crafting-sound',enabled?'on':'off') } catch { /* Session preference still works. */ }
  if(!enabled) stopCraftingSound()
}
export function prepareCraftingSound() {
  if(!craftingSoundEnabled())return
  try { context ||= new AudioContext(); void context.resume().catch(()=>{}) } catch { /* Animation works without audio. */ }
}
export function stopCraftingSound() {
  for(const voice of voices)try {voice.stop()} catch { /* Already ended. */ }
  voices.clear()
}
export function playCraftingSound(cue:'charge'|'reveal'|'collect') {
  if(!craftingSoundEnabled()||!context||context.state!=='running')return
  const audio=context, now=audio.currentTime
  const notes=cue==='charge'?[110,165,220]:cue==='reveal'?[523.25,659.25,783.99,1046.5]:[783.99,1046.5,1567.98]
  notes.forEach((frequency,index)=>{
    const start=now+index*(cue==='charge'?.06:.075),duration=cue==='charge'?1.05:cue==='reveal'?.9:.55
    const voice=audio.createOscillator(),gain=audio.createGain()
    voice.type=cue==='charge'?'sine':'triangle'
    voice.frequency.setValueAtTime(frequency,start)
    voice.frequency.exponentialRampToValueAtTime(frequency*(cue==='charge'?3:1.002),start+duration)
    gain.gain.setValueAtTime(0,start)
    gain.gain.linearRampToValueAtTime(.027/(index+1),start+.035)
    gain.gain.exponentialRampToValueAtTime(.0001,start+duration)
    voice.connect(gain);gain.connect(audio.destination);voices.add(voice)
    voice.onended=()=>{voices.delete(voice);voice.disconnect();gain.disconnect()}
    voice.start(start);voice.stop(start+duration)
  })
}
