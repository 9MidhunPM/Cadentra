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

  it('retries failed variant lookup in place without losing the selected line or draft values', async () => {
    let variantAttempts = 0;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === '/api/v1/products/product-1') {
        variantAttempts += 1;
        if (variantAttempts === 1) return response({ error: { code: 'UNAVAILABLE', message: 'Variants temporarily unavailable.' } }, 503);
        return response({ data: { id: 'product-1', name: 'Desk', variants: [{ id: 'variant-1', attribute_name: 'Tier', attribute_value: 'Plus', active: true }] } });
      }
      const items = path.startsWith('/api/v1/customers?') ? [{ id: 'customer-1', display_name: 'Example customer' }]
        : path.startsWith('/api/v1/plans?') ? [{ id: 'plan-1', name: 'Monthly seats', cadence: 'MONTHLY', min_quantity: 1 }]
        : path.startsWith('/api/v1/products?') ? [{ id: 'product-1', name: 'Desk', active: true }]
        : [{ id: 'template-1', name: 'Desk offer', plan_id: 'plan-1', valid_days: 14, lines: [{ product_id: 'product-1', variant_id: 'variant-1', quantity: 3 }] }];
      return response({ items, total: items.length, page: 1, page_size: 100 });
    }));
    render(<MemoryRouter><NewSubscription /></MemoryRouter>);
    await screen.findByRole('option', { name: 'Desk offer' });
    fireEvent.change(screen.getByLabelText('Customer'), { target: { value: 'customer-1' } });
    fireEvent.change(screen.getByLabelText('Service start (included)'), { target: { value: '2027-01-31' } });
    fireEvent.change(screen.getByLabelText('Service end (excluded)'), { target: { value: '2027-05-01' } });
    fireEvent.change(screen.getByLabelText('Payment terms (days)'), { target: { value: '14' } });
    fireEvent.change(screen.getByLabelText('Quotation template (optional)'), { target: { value: 'template-1' } });
    await screen.findByText('Variants temporarily unavailable.');
    fireEvent.change(screen.getByLabelText('Quantity 1'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('option', { name: 'Tier: Plus' });
    expect(variantAttempts).toBe(2);
    expect(screen.getByLabelText('Product 1')).toHaveValue('product-1');
    expect(screen.getByLabelText('Variant 1')).toHaveValue('variant-1');
    expect(screen.getByLabelText('Quantity 1')).toHaveValue(5);
    expect(screen.getByLabelText('Customer')).toHaveValue('customer-1');
    expect(screen.getByLabelText('Service start (included)')).toHaveValue('2027-01-31');
    expect(screen.getByLabelText('Service end (excluded)')).toHaveValue('2027-05-01');
    expect(screen.getByLabelText('Payment terms (days)')).toHaveValue(14);
  });

});
