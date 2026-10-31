import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { SessionProvider } from '../lib'
import { ToastProvider } from '../components/ui'
import { createAppRouter } from './router'
import '../styles/global.css'

const router = createAppRouter()
createRoot(document.getElementById('root')!).render(
  <StrictMode><SessionProvider><ToastProvider><RouterProvider router={router} /></ToastProvider></SessionProvider></StrictMode>,
)
