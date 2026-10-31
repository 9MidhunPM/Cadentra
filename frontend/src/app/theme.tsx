import { createContext, useCallback, useContext, useLayoutEffect, useState, type ReactNode } from 'react'

export type Theme = 'dark' | 'light'
export const THEME_STORAGE_KEY = 'cadentra:theme'

type ThemeContextValue = { theme: Theme; toggleTheme: () => void }
const ThemeContext = createContext<ThemeContextValue | null>(null)

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch {
    // Theme selection remains available when browser storage is blocked.
  }
  return 'dark'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState(() => ({ theme: initialTheme(), userSelected: false }))
  const toggleTheme = useCallback(() => {
    setSelection(current => ({ theme: current.theme === 'dark' ? 'light' : 'dark', userSelected: true }))
  }, [])

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = selection.theme
    document.documentElement.style.colorScheme = selection.theme
    // Reading a default must not write a preference the user never chose.
    if (selection.userSelected) {
      try { localStorage.setItem(THEME_STORAGE_KEY, selection.theme) } catch {
        // In-memory selection still works in restricted browser contexts.
      }
    }
  }, [selection])

  return <ThemeContext.Provider value={{ theme: selection.theme, toggleTheme }}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside ThemeProvider')
  return context
}
