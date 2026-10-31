import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { apiClient, ApiError } from '../../lib';
import { InvoiceDetail, PaymentForm } from './invoices';
import type { Invoice } from './types';

vi.mock('../../lib', async importOriginal => ({
  ...await importOriginal<typeof import('../../lib')>(),
  useSession: () => ({ actor: { id: 'polish-staff', role: 'STAFF', name: 'Staff', customer_id: null } }),
}));
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });

function invoice(id: string, status = 'DRAFT'): Invoice {
  return {
    id, number: 'INV-POLISH', customer_id: 'customer', status,
    collection_status: status === 'CONFIRMED' ? 'UNPAID' : status,
    currency: 'INR', invoice_date: '2026-10-31', due_date: '2026-11-07',
    period_start: '2026-10-31', period_end: '2026-11-30',
    subtotal: '100.00', discount_total: '0.00', tax_total: '0.00',
    total: '100.00', paid_amount: '0.00', balance_due: '100.00', payments: [], lines: [],
  };
}
function detail(id: string) {
  return render(<MemoryRouter initialEntries={[`/billing/invoices/${id}`]}><Routes><Route path="/billing/invoices/:id" element={<InvoiceDetail />} /></Routes></MemoryRouter>);
}

it.each(['DRAFT', 'CANCELLED'])('does not describe the stored %s balance as payable', async status => {
  const current = invoice(`polish-label-${status}`, status);
  vi.spyOn(apiClient, 'request').mockResolvedValue({ data: current });
  detail(current.id);
  await screen.findByText('Not payable');
  expect(screen.queryByText('Balance due')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Invoice summary')).toHaveTextContent('INR 100.00');
});

it('restores focus to the success notice when confirmation removes its trigger during reload', async () => {
  const id = 'polish-confirm';
  let reads = 0;
  let finishReload: (value: unknown) => void = () => { throw new Error('Reload has not started'); };
  vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
    if (options?.method === 'POST') return { data: invoice(id, 'CONFIRMED') };
    if (path === `/invoices/${id}` && ++reads > 1) return new Promise(resolve => { finishReload = resolve; });
    return { data: invoice(id) };
  });
  detail(id);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Confirm invoice' }));
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm' }));
  const notice = await screen.findByText('Invoice confirmed.');
  await waitFor(() => expect(notice).toHaveFocus());
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await act(async () => finishReload({ data: invoice(id, 'CONFIRMED') }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Confirm invoice' })).not.toBeInTheDocument());
  expect(notice).toHaveFocus();
});

it('keeps a rejected invoice action in its dialog without duplicating the page error', async () => {
  const id = 'polish-rejected';
  vi.spyOn(apiClient, 'request').mockImplementation(async (_path, options) => {
    if (options?.method === 'POST') throw new ApiError(409, 'INVALID_TRANSITION', 'This invoice changed. Reload before confirming.');
    return { data: invoice(id) };
  });
  detail(id);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Confirm invoice' }));
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm' }));
  await screen.findByText('This invoice changed. Reload before confirming.');
  expect(screen.getAllByRole('alert')).toHaveLength(1);
  expect(within(screen.getByRole('dialog')).getByRole('alert')).toHaveTextContent('This invoice changed.');
});

it('sends the original external-card enum when its human-readable option is selected', async () => {
  const current = invoice('polish-card', 'CONFIRMED');
  const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: current });
  render(<PaymentForm invoice={current} onSaved={() => undefined} />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText('Payment method'), screen.getByRole('option', { name: 'External card' }));
  await user.type(screen.getByLabelText('Amount'), '10.00');
  fireEvent.change(screen.getByLabelText('Payment date'), { target: { value: '2026-10-31' } });
  await user.type(screen.getByLabelText('Payment note'), 'Already received externally');
  await user.click(screen.getByRole('button', { name: 'Record payment' }));
  await waitFor(() => expect(request.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.json).toMatchObject({ method: 'CARD_EXTERNAL', amount: '10.00' }));
});
