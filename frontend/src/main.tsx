import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import './styles.css'
import './experience.css'
import './collection.css'
import { PackOpeningProvider } from './components/PackOpening'
import { SessionProvider } from './Session'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <SessionProvider><PackOpeningProvider><App /></PackOpeningProvider></SessionProvider>
    </HashRouter>
  </StrictMode>,
)
