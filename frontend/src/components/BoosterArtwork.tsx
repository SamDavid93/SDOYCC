import { useId } from 'react'
import './booster-artwork.css'

const palettes = [
  ['#87f0d0', '#247e79', '#102731'], ['#f3d399', '#b07a3c', '#30232c'],
  ['#bda7ff', '#7053af', '#231e38'], ['#91d6ff', '#377baf', '#11283b'],
  ['#ffa5a0', '#b34e62', '#341e30'], ['#c7eba4', '#65894c', '#1e3029'],
]

function titleLines(name: string) {
  const words = name.replace(/\s+Booster$/i, '').trim().split(/\s+/)
  const lines: string[] = []
  for (const word of words) {
    if (!lines.length || lines[lines.length - 1].length + word.length > 23) lines.push(word)
    else lines[lines.length - 1] += ' ' + word
  }
  return lines.length > 4 ? [...lines.slice(0, 3), lines[3].slice(0, 20) + '…'] : lines
}

/** Resolution-independent Hub packaging; never presented as a scan of a physical product. */
export function BoosterArtwork({ name, code }: { name: string; code?: string | null }) {
  const id = 'pack-' + useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const identity = name.replace(/\s+Booster$/i, '').trim().toLowerCase()
  const hash = Array.from(identity).reduce((value, char) => (Math.imul(value, 31) + char.charCodeAt(0)) >>> 0, 0)
  const [light, accent, dark] = palettes[hash % palettes.length]
  const lines = titleLines(name)
  return <svg className="sdoycc-pack-art" viewBox="0 0 320 480" role="img" aria-label={`SDOYCC-Cover: ${name}`} xmlns="http://www.w3.org/2000/svg">
    <title>{name} — SDOYCC-Sammeledition</title>
    <defs>
      <linearGradient id={id + '-base'} x2="1" y2="1"><stop stopColor={dark} /><stop offset=".5" stopColor="#101a29" /><stop offset="1" stopColor={dark} /></linearGradient>
      <linearGradient id={id + '-foil'} x2="1" y2=".4"><stop stopColor={accent} /><stop offset=".22" stopColor={light} /><stop offset=".5" stopColor="#edf7ee" /><stop offset=".72" stopColor={accent} /><stop offset="1" stopColor={light} /></linearGradient>
      <radialGradient id={id + '-glow'}><stop stopColor={accent} stopOpacity=".5" /><stop offset="1" stopColor={accent} stopOpacity="0" /></radialGradient>
      <linearGradient id={id + '-crystal'} x2="1" y2="1"><stop stopColor={light} /><stop offset=".5" stopColor={accent} /><stop offset="1" stopColor={dark} /></linearGradient>
      <pattern id={id + '-crimp'} width="6" height="20" patternUnits="userSpaceOnUse"><path d="M1 0v20" stroke="#fff" strokeOpacity=".18" /><path d="M4 0v20" stroke="#000" strokeOpacity=".25" /></pattern>
    </defs>
    <rect x="2" y="2" width="316" height="476" rx="5" fill={`url(#${id}-base)`} stroke={accent} strokeWidth="2" />
    <path d="M3 24h314V3H3zm0 432h314v21H3z" fill={`url(#${id}-foil)`} />
    <path d="M3 24h314V3H3zm0 432h314v21H3z" fill={`url(#${id}-crimp)`} />
    <rect x="16" y="36" width="288" height="407" rx="2" fill="none" stroke={light} strokeOpacity=".35" />
    <path d="M16 94V36h58M246 36h58v58M16 385v58h58M246 443h58v-58" fill="none" stroke={light} strokeWidth="2" />
    <text x="160" y="76" textAnchor="middle" fill="#f1f6f6" fontSize="32" fontWeight="800" letterSpacing="4">SDOYCC</text>
    <text x="160" y="96" textAnchor="middle" fill={light} fontSize="9" letterSpacing="3.5">DEINE KARTEN. DEINE STRATEGIE.</text>
    <circle cx="160" cy="225" r="118" fill={`url(#${id}-glow)`} />
    <g fill="none" stroke={light}>
      <circle cx="160" cy="224" r="88" strokeOpacity=".16" /><circle cx="160" cy="224" r="70" strokeOpacity=".5" />
      <path d="M160 123v20m0 162v20M59 224h20m162 0h20M88 152l14 14m116 116 14 14M88 296l14-14m116-116 14-14" strokeOpacity=".65" />
      <path d="m160 137 87 87-87 87-87-87z" strokeOpacity=".25" />
    </g>
    <path d="m160 162 49 62-49 62-49-62z" fill={`url(#${id}-crystal)`} stroke={light} strokeWidth="1.5" />
    <path d="m160 162-18 62 18 62 18-62z" fill={light} fillOpacity=".2" stroke={light} strokeOpacity=".55" />
    <path d="M111 224h98M142 224l18-14 18 14-18 14z" fill="none" stroke={light} strokeOpacity=".75" />
    <path d="m155 132 5-8 5 8-5 8zm0 180 5-8 5 8-5 8z" fill={light} />
    <path d="M38 330h244" stroke={light} strokeOpacity=".3" />
    {lines.map((line, index) => <text key={index} x="160" y={357 + index * 21} textAnchor="middle" fill="#f2f6f8" fontSize="17" fontWeight="650">{line}</text>)}
    <text x="160" y="432" textAnchor="middle" fill={light} fontSize="9" letterSpacing="2">{code ? code.toUpperCase().slice(0, 28) : 'SDOYCC SAMMELEDITION'}</text>
    <path d="M3 25 206 25 3 290z" fill="#fff" fillOpacity=".035" />
  </svg>
}
