import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from './theme'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  document.documentElement.style.removeProperty('color-scheme')
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
  delete document.documentElement.dataset.theme
  document.documentElement.style.removeProperty('color-scheme')
})

describe('theme preference', () => {
  it('defaults to dark independently of OS preference without storing a selection', () => {
    const matchMedia = vi.fn(() => ({ matches: false }))
    vi.stubGlobal('matchMedia', matchMedia)
    const save = vi.spyOn(Storage.prototype, 'setItem')
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(matchMedia).not.toHaveBeenCalled()
    expect(save).not.toHaveBeenCalled()
  })

  it.each(['dark', 'light'] as const)('restores saved %s without rewriting storage', theme => {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
    const save = vi.spyOn(Storage.prototype, 'setItem')
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    expect(result.current.theme).toBe(theme)
    expect(document.documentElement.dataset.theme).toBe(theme)
    expect(document.documentElement.style.colorScheme).toBe(theme)
    expect(save).not.toHaveBeenCalled()
  })

  it('ignores an invalid saved preference without overwriting it', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'system')
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    expect(result.current.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system')
  })

  it('persists user toggles and restores the selection on remount', () => {
    const first = renderHook(useTheme, { wrapper: ThemeProvider })
    act(() => first.result.current.toggleTheme())
    expect(first.result.current.theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    first.unmount()
    const second = renderHook(useTheme, { wrapper: ThemeProvider })
    expect(second.result.current.theme).toBe('light')
    act(() => second.result.current.toggleTheme())
    expect(second.result.current.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('supports batched toggles without losing the explicit user preference', () => {
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    act(() => {
      result.current.toggleTheme()
      result.current.toggleTheme()
    })
    expect(result.current.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('defaults and toggles in memory when localStorage is inaccessible', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => { throw new DOMException('Blocked', 'SecurityError') })
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    expect(result.current.theme).toBe('dark')
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
  })

  it('keeps a chosen theme when storage writes fail', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError') })
    const { result } = renderHook(useTheme, { wrapper: ThemeProvider })
    act(() => result.current.toggleTheme())
    expect(result.current.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
  })
})
