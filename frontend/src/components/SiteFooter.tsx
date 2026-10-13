import { useEffect, useRef } from 'react'
import './site-footer.css'

export function SiteFooter() {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const footer = ref.current
    const parent = footer?.parentElement
    if (!footer || !parent) return
    const update = () => parent.style.setProperty('--site-footer-height', `${footer.getBoundingClientRect().height}px`)
    const observer = new ResizeObserver(update)
    observer.observe(footer)
    update()
    return () => { observer.disconnect(); parent.style.removeProperty('--site-footer-height') }
  }, [])
  return <footer ref={ref} className="site-footer" aria-label="Copyright notice">
    <p>The literal and graphical information presented on this site about Yu-Gi-Oh!, including card images, the attribute, level/rank and type symbols, and card text, is copyright 4K Media Inc, a subsidiary of Konami Digital Entertainment, Inc. This website is not produced by, endorsed by, supported by, or affiliated with 4k Media or Konami Digital Entertainment.</p>
  </footer>
}
