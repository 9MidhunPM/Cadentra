/** Focused form recovery tests; API responses are test-only fixtures. */
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../lib';
import { fieldError, NewSubscription, TemplateEditor } from './forms';

afterEach(() => vi.unstubAllGlobals());

const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

describe('subscription field validation', () => {
  it.each([
    ['start_date', { start_date: 'Select a service date.' }, 'Select a service date.'],
    ['start_date', { 'body.start_date': 'Select a service date.' }, 'Select a service date.'],
    ['lines.0.quantity', { 'body.lines.0.quantity': ['Use a positive quantity.'] }, 'Use a positive quantity.'],
    ['lines', { 'body.lines': 'Include a product line.' }, 'Include a product line.'],
  ])('supports plain or body-prefixed %s errors', (field, fields, expected) => {
    expect(fieldError(new ApiError(422, 'VALIDATION_ERROR', 'Check fields.', fields), field)).toBe(expected);
  });

  it('ignores non-API errors and missing field details', () => {
    expect(fieldError(new Error('Unavailable'), 'lines')).toBeUndefined();
    expect(fieldError(new ApiError(422, 'VALIDATION_ERROR', 'Check fields.'), 'lines')).toBeUndefined();
  });
});

describe('subscription option loading recovery', () => {
  it.each(['subscription', 'template'])('retries failed %s catalog lookups without a page reload', async (kind) => {
    let unavailable = true;
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.startsWith('/api/v1/customers?') && unavailable) {
        return response({ error: { code: 'UNAVAILABLE', message: 'Options are temporarily unavailable.' } }, 503);
      }
      const items = path.startsWith('/api/v1/plans?')
        ? [{ id: 'plan-1', name: 'Monthly seats', cadence: 'MONTHLY', min_quantity: 1 }]
        : [];
      return response({ items, total: items.length, page: 1, page_size: 100 });
    });
    vi.stubGlobal('fetch', fetcher);
    render(<MemoryRouter>{kind === 'subscription' ? <NewSubscription /> : <TemplateEditor />}</MemoryRouter>);
    expect(await screen.findByText('Options are temporarily unavailable.')).toBeInTheDocument();
    unavailable = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('option', { name: /Monthly seats/ })).toBeInTheDocument();
    expect(screen.queryByText('Options are temporarily unavailable.')).not.toBeInTheDocument();
    expect(fetcher.mock.calls.filter(call => String(call[0]).startsWith('/api/v1/customers?'))).toHaveLength(2);
  });
});
