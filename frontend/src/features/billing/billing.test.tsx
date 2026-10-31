/** UI fixtures only: these tests do not establish live API or PostgreSQL correctness. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes, useRoutes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, ApiError } from '../../lib';
import { InvoiceDetail, InvoiceList, PaymentForm } from './invoices';
import { RulePage } from './rules';
import { getRoutes } from './index';
import type { Invoice } from './types';

const session = vi.hoisted(() => ({ role: 'STAFF' }));
vi.mock('../../lib', async importOriginal => ({
  ...await importOriginal<typeof import('../../lib')>(),
  useSession: () => ({ actor: { id: 'staff', role: session.role, name: 'Staff', customer_id: null } }),
}));
afterEach(() => { vi.restoreAllMocks(); session.role = 'STAFF'; });
const invoice: Invoice = { id: 'inv', number: 'INV-1', customer_id: 'customer', status: 'CONFIRMED', collection_status: 'UNPAID', currency: 'INR', invoice_date: '2026-10-31', due_date: '2026-11-07', period_start: '2026-10-31', period_end: '2026-11-30', subtotal: '4680.00', discount_total: '468.00', tax_total: '758.16', total: '4970.16', paid_amount: '0.00', balance_due: '4970.16', payments: [] };

async function fillPayment() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Amount'), '2000.00');
  fireEvent.change(screen.getByLabelText('Payment date'), { target: { value: '2026-10-31' } });
  await user.type(screen.getByLabelText('Payment note'), 'Received by transfer');
  return user;
}

describe('billing feature interactions', () => {
  it('labels SENT as SMTP acceptance rather than verified external delivery', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { ...invoice, email_status: 'SENT', lines: [] } });
    render(<MemoryRouter initialEntries={['/billing/invoices/inv']}><Routes><Route path="/billing/invoices/:id" element={<InvoiceDetail />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('Accepted by SMTP (external delivery unverified)')).toBeInTheDocument();
  });

  it('preserves payment payload and idempotency key after an uncertain result', async () => {
    const request = vi.spyOn(apiClient, 'request').mockRejectedValueOnce(new ApiError(0, 'NETWORK_ERROR', 'Cannot reach server')).mockResolvedValueOnce({ data: { id: 'payment' } });
    const saved = vi.fn();
    render(<PaymentForm invoice={invoice} onSaved={saved} />);
    const user = await fillPayment();
    await user.click(screen.getByRole('button', { name: 'Record payment' }));
    expect(await screen.findByText(/result is uncertain/)).toBeInTheDocument();
    expect(screen.getByLabelText('Amount')).toBeDisabled();
    const first = request.mock.calls[0][1]?.json;
    await user.click(screen.getByRole('button', { name: 'Retry same payment' }));
    await waitFor(() => expect(saved).toHaveBeenCalledOnce());
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[1][1]?.json).toEqual(first);
    expect(first).toMatchObject({ amount: '2000.00', paid_on: '2026-10-31', note: 'Received by transfer', method: 'BANK_TRANSFER' });
    expect(first).not.toHaveProperty('total');
  });
  it('blocks duplicate payment submissions while pending', async () => {
    let finish: (value: unknown) => void = () => undefined;
    const request = vi.spyOn(apiClient, 'request').mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    render(<PaymentForm invoice={invoice} onSaved={() => undefined} />);
    const user = await fillPayment();
    await user.click(screen.getByRole('button', { name: 'Record payment' }));
    expect(screen.getByRole('button', { name: 'Retry same payment' })).toBeDisabled();
    expect(request).toHaveBeenCalledOnce();
    finish({ data: { id: 'payment' } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Record payment' })).toBeEnabled());
  });
  it('allows editing a definitively rejected payment rather than silently replacing its key', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(422, 'VALIDATION_ERROR', 'Amount is invalid', { 'body.amount': 'Use a positive amount.' }));
    render(<PaymentForm invoice={invoice} onSaved={() => undefined} />);
    const user = await fillPayment();
    await user.click(screen.getByRole('button', { name: 'Record payment' }));
    expect(await screen.findByText('Use a positive amount.')).toBeInTheDocument();
    expect(screen.getByLabelText('Amount')).toHaveAttribute('aria-invalid', 'true');
    await user.click(await screen.findByRole('button', { name: 'Edit rejected payment' }));
    expect(screen.getByLabelText('Amount')).toBeEnabled();
    expect(screen.getByLabelText('Amount')).toHaveValue('2000.00');
  });
  it('shows readable errors and explicitly retries invoice reads', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValueOnce(new ApiError(403, 'FORBIDDEN', 'You do not have permission.')).mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 25 });
    render(<MemoryRouter><InvoiceList /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('You do not have permission.');
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No invoices match these filters')).toBeInTheDocument();
  });
  it('renders server money and sends filters with server pagination', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ items: [invoice], total: 26, page: 1, page_size: 25 });
    render(<MemoryRouter><InvoiceList /></MemoryRouter>);
    expect(await screen.findAllByText('INR 4,970.16')).toHaveLength(2);
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(request.mock.calls.at(-1)?.[0]).toContain('page=2'));
    fireEvent.change(screen.getByLabelText('Invoice status'), { target: { value: 'PAID' } });
    await waitFor(() => expect(request.mock.calls.at(-1)?.[0]).toContain('status=PAID'));
    expect(request.mock.calls.at(-1)?.[0]).toContain('page=1');
  });
  it('keeps rule writes unavailable to staff', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    render(<RulePage kind="discount" />);
    expect(await screen.findByText('No discount rules configured')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create discount rule' })).not.toBeInTheDocument();
    expect(screen.getByText(/Read-only configuration/)).toBeInTheDocument();
  });
  it('sends decimal tax values and real selected catalogue identities from admin form', async () => {
    session.role = 'ADMIN';
    const request = vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 25 })
      .mockResolvedValueOnce({ items: [{ id: 'product-1', name: 'Suite' }], total: 1, page: 1, page_size: 100 })
      .mockResolvedValueOnce({ data: { id: 'tax', effective_from: '2026-10-31' } })
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Create tax rule' }));
    await user.type(screen.getByLabelText('Rule name'), 'Illustrative tax');
    await user.type(screen.getByLabelText('Tax rate (%)'), '18.1250');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.click(await screen.findByLabelText('Suite'));
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    await waitFor(() => expect(request.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(true));
    expect(request.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.json).toMatchObject({ rate_percent: '18.1250', product_ids: ['product-1'] });
  });
  it('does not carry tax revision state into the discount route', async () => {
    session.role = 'ADMIN';
    vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ items: [{ id: 'tax-id', name: 'Tax editing fixture', rate_percent: '18.0000', active: true, valid_from: '2026-10-31', effective_from: '2026-10-31' }], total: 1, page: 1, page_size: 25 })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 })
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    function BillingRoutes() { return useRoutes(getRoutes()); }
    render(<MemoryRouter initialEntries={['/billing/taxes']}><Link to="/billing/discounts">Go to discounts</Link><BillingRoutes /></MemoryRouter>);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Schedule revision' }));
    expect(screen.getByLabelText('Rule name')).toHaveValue('Tax editing fixture');
    await user.click(screen.getByRole('link', { name: 'Go to discounts' }));
    expect(await screen.findByRole('heading', { name: 'Discount rules' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Schedule a retained revision' })).not.toBeInTheDocument();
    const create = screen.getByRole('button', { name: 'Create discount rule' });
    await waitFor(() => expect(create).toBeEnabled());
    await user.click(create);
    expect(screen.getByLabelText('Rule name')).toHaveValue('');
    expect(screen.queryByLabelText('Revision effective from')).not.toBeInTheDocument();
  });

  it.each([
    ['network', new ApiError(0, 'NETWORK_ERROR', 'Connection lost')],
    ['server', new ApiError(500, 'HTTP_500', 'Server error')],
    ['response', new ApiError(200, 'INVALID_RESPONSE', 'Unreadable response')],
    ['malformed success', null],
  ])('blocks another rule creation after uncertain %s outcome until explicit reconciliation', async (_label, failure) => {
    session.role = 'ADMIN';
    const request = vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 25 })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 });
    if (failure) request.mockRejectedValueOnce(failure);
    else request.mockResolvedValueOnce({ data: null });
    request.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    const view = render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    const create = screen.getByRole('button', { name: 'Create tax rule' });
    await waitFor(() => expect(create).toBeEnabled());
    await user.click(create);
    await user.type(screen.getByLabelText('Rule name'), 'Uncertain tax');
    await user.type(screen.getByLabelText('Tax rate (%)'), '18.00');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    expect(await screen.findByText(/previous rule request may have succeeded/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create rule' })).toBeDisabled();
    expect(screen.getByLabelText('Rule name')).toBeDisabled();
    const form = screen.getByLabelText('Rule name').closest('form');
    if (!form) throw new Error('Rule form missing');
    fireEvent.submit(form);
    await user.click(screen.getByRole('button', { name: 'Close form' }));
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    view.rerender(<RulePage key="remounted" kind="tax" />);
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    request.mockRejectedValueOnce(new ApiError(0, 'NETWORK_ERROR', 'Rule list still unavailable'));
    await user.click(screen.getByRole('button', { name: 'Reload rule list to reconcile' }));
    expect(await screen.findByText('Rule list still unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Reload rule list to reconcile' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
    expect(screen.queryByLabelText('Rule name')).not.toBeInTheDocument();
  });

  it('keeps a definitively rejected rule editable for correction', async () => {
    session.role = 'ADMIN';
    const request = vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 25 })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 })
      .mockRejectedValueOnce(new ApiError(422, 'VALIDATION_ERROR', 'Check the submitted fields.', { 'body.rate_percent': 'Rate must not exceed 100.' }))
      .mockResolvedValueOnce({ data: { id: 'tax', effective_from: '2026-10-31' } })
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Create tax rule' }));
    await user.type(screen.getByLabelText('Rule name'), 'Corrected tax');
    await user.type(screen.getByLabelText('Tax rate (%)'), '101');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    expect(await screen.findByText('Rate must not exceed 100.')).toBeInTheDocument();
    expect(screen.getByLabelText('Tax rate (%)')).toBeEnabled();
    await user.clear(screen.getByLabelText('Tax rate (%)'));
    await user.type(screen.getByLabelText('Tax rate (%)'), '18');
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    await waitFor(() => expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(2));
  });

  it('preserves a valid zero usage cap when scheduling an existing discount revision', async () => {
    session.role = 'ADMIN';
    const zeroRule = { id: 'discount-id', name: 'Zero cap', active: true, kind: 'PERCENT', value: '10.0000', scope: 'SUBSCRIPTION', min_purchase: '0.00', min_quantity: 0, starts_on: '2026-10-31', usage_limit: 0, uses_count: 0, effective_from: '2026-10-31' };
    const request = vi.spyOn(apiClient, 'request')
      .mockResolvedValueOnce({ items: [zeroRule], total: 1, page: 1, page_size: 25 })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100 })
      .mockResolvedValueOnce({ data: { ...zeroRule, effective_from: '2026-11-01' } })
      .mockResolvedValue({ items: [zeroRule], total: 1, page: 1, page_size: 25 });
    render(<RulePage kind="discount" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Schedule revision' }));
    const limit = screen.getByLabelText('Global usage limit (optional)');
    expect(limit).toHaveValue(0);
    expect(limit).toHaveAttribute('min', '0');
    fireEvent.change(screen.getByLabelText('Revision effective from'), { target: { value: '2026-11-01' } });
    const submit = screen.getAllByRole('button', { name: 'Schedule revision' }).find(button => button.getAttribute('type') === 'submit');
    if (!submit) throw new Error('Revision submit button missing');
    await user.click(submit);
    await waitFor(() => expect(request.mock.calls.some(([, options]) => options?.method === 'PATCH')).toBe(true));
    expect(request.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.json).toMatchObject({ usage_limit: 0 });
  });

  it('broadcasts a pending write across navigation and blocks reconciliation until failure settles', async () => {
    session.role = 'ADMIN';
    let failPost: (error: unknown) => void = () => undefined;
    const pendingPost = new Promise<unknown>((_resolve, reject) => { failPost = reject; });
    const empty = { items: [], total: 0, page: 1, page_size: 25 };
    const request = vi.spyOn(apiClient, 'request').mockResolvedValueOnce(empty).mockResolvedValueOnce(empty).mockReturnValueOnce(pendingPost).mockResolvedValue(empty);
    function BillingRoutes() { return useRoutes(getRoutes()); }
    render(<MemoryRouter initialEntries={['/billing/taxes']}><Link to="/billing/taxes">Tax navigation</Link><Link to="/billing/discounts">Discount navigation</Link><BillingRoutes /></MemoryRouter>);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Create tax rule' }));
    await user.type(screen.getByLabelText('Rule name'), 'Pending tax');
    await user.type(screen.getByLabelText('Tax rate (%)'), '18');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    await user.click(screen.getByRole('link', { name: 'Discount navigation' }));
    await user.click(screen.getByRole('link', { name: 'Tax navigation' }));
    expect(await screen.findByText(/request is still in progress/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Reload rule list to reconcile' })).not.toBeInTheDocument();
    failPost(new ApiError(0, 'NETWORK_ERROR', 'Connection lost'));
    expect(await screen.findByText(/previous rule request may have succeeded/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Reload rule list to reconcile' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('keeps a remounted page blocked after success until a fresh list arrives and ignores an older read', async () => {
    session.role = 'ADMIN';
    let finishPost: (value: unknown) => void = () => undefined;
    let finishOldRead: (value: unknown) => void = () => undefined;
    let finishFreshRead: (value: unknown) => void = () => undefined;
    const post = new Promise<unknown>(resolve => { finishPost = resolve; });
    const oldRead = new Promise<unknown>(resolve => { finishOldRead = resolve; });
    const freshRead = new Promise<unknown>(resolve => { finishFreshRead = resolve; });
    const empty = { items: [], total: 0, page: 1, page_size: 25 };
    const request = vi.spyOn(apiClient, 'request').mockResolvedValueOnce(empty).mockResolvedValueOnce(empty).mockReturnValueOnce(post).mockResolvedValueOnce(empty).mockReturnValueOnce(oldRead).mockReturnValueOnce(freshRead).mockResolvedValue(empty);
    function BillingRoutes() { return useRoutes(getRoutes()); }
    render(<MemoryRouter initialEntries={['/billing/taxes']}><Link to="/billing/taxes">Tax navigation</Link><Link to="/billing/discounts">Discount navigation</Link><BillingRoutes /></MemoryRouter>);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Create tax rule' }));
    await user.type(screen.getByLabelText('Rule name'), 'Created while away');
    await user.type(screen.getByLabelText('Tax rate (%)'), '18');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    await user.click(screen.getByRole('link', { name: 'Discount navigation' }));
    await user.click(screen.getByRole('link', { name: 'Tax navigation' }));
    const created = { id: 'new-tax', name: 'Created while away', active: true, rate_percent: '18.0000', effective_from: '2026-10-31' };
    finishPost({ data: created });
    expect(await screen.findByText(/Refreshing the list before another request/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeDisabled();
    finishFreshRead({ items: [created], total: 1, page: 1, page_size: 25 });
    expect(await screen.findByText('Created while away')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create tax rule' })).toBeEnabled());
    finishOldRead(empty);
    await waitFor(() => expect(screen.getByText('Created while away')).toBeInTheDocument());
    expect(request.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

});
