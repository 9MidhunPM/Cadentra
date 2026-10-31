/** Test-only API fixtures. These checks do not establish backend/browser integration. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../lib';
import { ActionForm, SubscriptionDetail, SubscriptionList } from './pages';
import { NewSubscription } from './forms';
import type { Subscription } from './types';

const record: Subscription = { id: 'sub-1', number: 'SUB-000001', customer_id: 'customer-1', plan_id: 'plan-1', state: 'QUOTATION', start_date: '2027-01-31', end_date: '2027-05-01', payment_terms_days: 14, currency: 'INR', revision: 1, plan_snapshot: { name: 'Monthly seats', base_fee: '35.00' }, lines: [], allowed_actions: ['confirm'] };
const list = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 100 });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => apiClient.setCsrfToken(null));
afterEach(() => vi.unstubAllGlobals());

describe('subscription staff forms', () => {
  it.each([['QUOTE_EXPIRED', 'Revise this expired quotation.'], ['QUOTATION_PLAN_CHANGED', 'The quoted plan terms changed.']])('preserves acknowledgement and explains confirmation conflict %s', async (code, message) => {
    const saved = vi.fn();
    const fetcher = vi.fn().mockResolvedValue(response({ error: { code, message } }, 409));
    vi.stubGlobal('fetch', fetcher);
    render(<ActionForm action="confirm" record={record} onSaved={saved} />);
    const submit = screen.getByRole('button', { name: 'Confirm quotation' });
    expect(submit).toBeDisabled();
    expect(screen.getByText(/shortened final period is charged at the full-cycle price/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(submit);
    await screen.findByText(message);
    if (code === 'QUOTATION_PLAN_CHANGED') expect(screen.getByText(/review the updated plan terms/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeChecked();
    expect(saved).not.toHaveBeenCalled();
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({});
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/subscriptions/sub-1/confirm');
  });

  it('copies a template into reviewed line overrides and retains entries after server validation', async () => {
    let submitted: unknown;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (init?.method === 'POST') { submitted = JSON.parse(String(init.body)); return response({ error: { code: 'VALIDATION_ERROR', message: 'Check service dates.', fields: { start_date: 'Choose a valid service date.' } } }, 422); }
      if (path.startsWith('/api/v1/customers?')) return response(list([{ id: 'customer-1', display_name: 'Example customer' }]));
      if (path.startsWith('/api/v1/plans?')) return response(list([{ id: 'plan-1', name: 'Monthly seats', cadence: 'MONTHLY', min_quantity: 3 }]));
      if (path.startsWith('/api/v1/products?')) return response(list([{ id: 'product-1', name: 'Desk', active: true }]));
      if (path.startsWith('/api/v1/quotation-templates?')) return response(list([{ id: 'template-1', name: 'Three seats', plan_id: 'plan-1', valid_days: 7, lines: [{ product_id: 'product-1', variant_id: 'variant-1', quantity: 3 }] }]));
      if (path === '/api/v1/products/product-1') return response({ data: { id: 'product-1', name: 'Desk', variants: [{ id: 'variant-1', attribute_name: 'Tier', attribute_value: 'Plus', active: true }] } });
      throw new Error(`Unexpected test request ${path}`);
    }));
    render(<MemoryRouter><NewSubscription /></MemoryRouter>);
    await screen.findByRole('option', { name: 'Three seats' });
    fireEvent.change(screen.getByLabelText('Customer'), { target: { value: 'customer-1' } });
    fireEvent.change(screen.getByLabelText('Quotation template (optional)'), { target: { value: 'template-1' } });
    await screen.findByRole('option', { name: 'Tier: Plus' });
    expect(screen.getByLabelText('Quantity 1')).toHaveValue(3);
    expect(screen.getByLabelText('Variant 1')).toHaveValue('variant-1');
    fireEvent.change(screen.getByLabelText('Service start (included)'), { target: { value: '2027-01-31' } });
    fireEvent.change(screen.getByLabelText('Service end (excluded)'), { target: { value: '2027-05-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }));
    await screen.findByText('Choose a valid service date.');
    expect(screen.getByLabelText('Service start (included)')).toHaveValue('2027-01-31');
    expect(screen.getByLabelText('Quantity 1')).toHaveValue(3);
    expect(submitted).toEqual({ customer_id: 'customer-1', plan_id: 'plan-1', template_id: 'template-1', start_date: '2027-01-31', end_date: '2027-05-01', payment_terms_days: 0, lines: [{ product_id: 'product-1', variant_id: 'variant-1', quantity: 3 }] });
  });

  it('sends filters to the API and renders server-provided amounts without local arithmetic', async () => {
    const fetcher = vi.fn().mockImplementation(async () => response({ items: [{ ...record, recurring_subtotal: '4715.00', customer_name: 'Example customer' }], total: 1, page: 1, page_size: 25 }));
    vi.stubGlobal('fetch', fetcher);
    render(<MemoryRouter><Routes><Route path="*" element={<SubscriptionList />} /></Routes></MemoryRouter>);
    await screen.findByText('SUB-000001');
    expect(screen.getByText('INR 4,715.00')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search subscriptions'), { target: { value: 'Example customer' } });
    fireEvent.change(screen.getByLabelText('State'), { target: { value: 'QUOTATION' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply filters' }));
    await waitFor(() => expect(fetcher.mock.calls.some(call => String(call[0]).includes('q=Example+customer') && String(call[0]).includes('state=QUOTATION'))).toBe(true));
  });

  it('shows a closed past term without a pending-closure label and uses the server line amount', async () => {
    const closed = { ...record, state: 'CLOSED', expired: true, allowed_actions: [], lines: [{ id: 'line-1', product_id: 'product-1', description: 'Desk seats', quantity: 3, unit_price: '1560.00', line_total: '4680.00' }, { id: 'line-2', product_id: 'product-2', description: 'No server total supplied', quantity: 2, unit_price: '100.00' }] };
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => response({ data: closed })));
    render(<MemoryRouter initialEntries={['/subscriptions/sub-1']}><Routes><Route path="/subscriptions/:id" element={<SubscriptionDetail />} /></Routes></MemoryRouter>);
    await screen.findByText('Desk seats');
    expect(screen.queryByText('Expired, closure pending')).not.toBeInTheDocument();
    expect(screen.getByText('INR 4,680.00')).toBeInTheDocument();
    expect(screen.queryByText('INR 200.00')).not.toBeInTheDocument();
    expect(screen.getByText('Line amount · before tax and discounts')).toBeInTheDocument();
  });


  it('uses persisted quotation validity and submits an explicit override without deriving dates', async () => {
    const saved = vi.fn();
    const fetcher = vi.fn().mockImplementation(async () => response({ data: { ...record, quotation_valid_days: 21 } }));
    vi.stubGlobal('fetch', fetcher);
    render(<ActionForm action="issue-quotation" record={{ ...record, state: 'DRAFT', quotation_valid_days: 14 }} onSaved={saved} />);
    const validity = screen.getByLabelText('Validity in days');
    expect(validity).toHaveValue(14);
    fireEvent.change(validity, { target: { value: '21' } });
    fireEvent.click(screen.getByRole('button', { name: 'Issue quotation' }));
    await waitFor(() => expect(saved).toHaveBeenCalledTimes(1));
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/subscriptions/sub-1/issue-quotation');
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ valid_days: 21 });
  });


  it('does not offer next-cycle edits for an active term with no eligible cycle', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => response({ data: { ...record, state: 'ACTIVE', expired: true, next_billing_date: null, allowed_actions: ['close'], lines: [] } })));
    render(<MemoryRouter initialEntries={['/subscriptions/sub-1']}><Routes><Route path="/subscriptions/:id" element={<SubscriptionDetail />} /></Routes></MemoryRouter>);
    await screen.findByText('Expired, closure pending');
    expect(screen.queryByRole('button', { name: 'Change next-cycle lines' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close subscription' })).toBeInTheDocument();
  });


  it('displays server tax references and preview basis without calculating tax amounts', async () => {
    const detail = { ...record, tax_preview_on: '2027-01-31', tax_preview_basis: 'Period-rule preview only; stored invoice amounts are authoritative.', base_fee_taxes: [], lines: [{ product_id: 'product-1', description: 'Taxed seats', quantity: 3, unit_price: '1560.00', line_total: '4680.00', taxes: [{ id: 'tax-1', name: 'Example service tax', rate_percent: '18.0000' }] }, { product_id: 'product-2', description: 'Legacy line', quantity: 1, unit_price: '10.00' }] };
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => response({ data: detail })));
    render(<MemoryRouter initialEntries={['/subscriptions/sub-1']}><Routes><Route path="/subscriptions/:id" element={<SubscriptionDetail />} /></Routes></MemoryRouter>);
    await screen.findByText('Example service tax (18.0000%)');
    expect(screen.getByText('No applicable tax rules')).toBeInTheDocument();
    expect(screen.getByText('Resolved on invoice')).toBeInTheDocument();
    expect(screen.getByText(/stored invoice amounts are authoritative/)).toBeInTheDocument();
    expect(screen.getByText('Line amount · before tax and discounts')).toBeInTheDocument();
    expect(screen.queryByText('INR 842.40')).not.toBeInTheDocument();
  });

});
