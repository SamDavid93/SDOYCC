import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import './styles.css'
import './experience.css'
import './collection.css'
import './catalog-density.css'
import './master-duel-theme.css'
import './master-duel-content.css'
import './master-duel-game.css'
import { PackOpeningProvider } from './components/PackOpening'
import { SessionProvider } from './Session'
import { InteractionPolicy } from './components/InteractionPolicy'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <InteractionPolicy />
    <HashRouter>
      <SessionProvider><PackOpeningProvider><App /></PackOpeningProvider></SessionProvider>
    </HashRouter>
  </StrictMode>,
)
