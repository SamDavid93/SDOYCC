import { useEffect } from 'react'

export function InteractionPolicy() {
  useEffect(() => {
    const suppressBrowserMenu = (event: MouseEvent) => event.preventDefault()
    // Do not stop propagation: deck removal and duel shortcuts keep working.
    document.addEventListener('contextmenu', suppressBrowserMenu, {capture: true})
    return () => document.removeEventListener('contextmenu', suppressBrowserMenu, {capture: true})
  }, [])
  return null
}
