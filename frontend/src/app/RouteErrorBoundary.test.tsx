import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { RouteErrorBoundary } from './RouteErrorBoundary'

describe('route recovery', () => {
  it('hides loader errors, focuses an explanation and offers working navigation', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const router = createMemoryRouter([{
      errorElement: <RouteErrorBoundary />,
      children: [
        { path: '/', element: <h1>Workspace home</h1> },
        { path: '/broken', loader: () => { throw new Error('PRIVATE_STACK_AND_RECORD_DATA') }, element: <h1>Never shown</h1> },
      ],
    }], { initialEntries: ['/broken'] })
    render(<RouterProvider router={router} />)
    const heading = await screen.findByRole('heading', { name: 'We couldn’t open this page' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(document.title).toBe('Page unavailable · Cadentra')
    expect(screen.queryByText(/PRIVATE_STACK/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Return to your workspace' }))
    expect(await screen.findByRole('heading', { name: 'Workspace home' })).toBeVisible()
  })
})
