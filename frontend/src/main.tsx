import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './api/http' // side-effect: sets axios baseURL before any request
import './index.css'
import { AppShell } from './components/AppShell.tsx'
import { CartDrawer } from './components/CartDrawer.tsx'
import { CartUIProvider } from './context/CartUIContext.tsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <CartUIProvider>
          <AppShell />
          <CartDrawer />
        </CartUIProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
