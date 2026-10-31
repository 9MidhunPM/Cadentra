import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { SessionProvider } from '../lib'
import { ToastProvider } from '../components/ui'
import { createAppRouter } from './router'
import { ThemeProvider } from './theme'
import { LazyMotion, MotionConfig } from 'motion/react'
import '../styles/global.css'

const router = createAppRouter()
const loadMotionFeatures = () => import('./motion-features').then(module => module.default)
createRoot(document.getElementById('root')!).render(
  <StrictMode><ThemeProvider><MotionConfig reducedMotion="user"><LazyMotion features={loadMotionFeatures} strict><SessionProvider><ToastProvider><RouterProvider router={router} /></ToastProvider></SessionProvider></LazyMotion></MotionConfig></ThemeProvider></StrictMode>,
)
