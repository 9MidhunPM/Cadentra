import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, useLocation, useNavigate } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { apiClient } from '../../lib';
import { InvoiceList } from './invoices';

afterEach(() => vi.restoreAllMocks());

function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  return <>
    <output aria-label="Current invoice query">{location.search}</output>
    <button onClick={() => navigate(-1)}>Back</button>
    <button onClick={() => navigate(1)}>Forward</button>
    <Link to="/billing/invoices?customer_id=customer-b&status=PAID&page=2">Open another drilldown</Link>
  </>;
}
function setup() {
  const request = vi.spyOn(apiClient, 'request').mockImplementation(async path => path.startsWith('/customers?')
    ? { items: [{ id: 'customer-a', display_name: 'Customer A' }, { id: 'customer-b', display_name: 'Customer B' }], total: 2, page: 1, page_size: 100 }
    : { items: [], total: 0, page: 1, page_size: 25 });
  render(<MemoryRouter initialEntries={['/billing/invoices?page=4']}><Navigation /><InvoiceList /></MemoryRouter>);
  return request;
}
function query() { return new URLSearchParams(screen.getByLabelText('Current invoice query').textContent ?? ''); }

it('composes rapid filter changes without dropping the selected customer and restores each history state', async () => {
  const request = setup();
  await screen.findByRole('option', { name: 'Customer A' });
  act(() => {
    fireEvent.change(screen.getByLabelText('Customer'), { target: { value: 'customer-a' } });
    fireEvent.change(screen.getByLabelText('Invoice status'), { target: { value: 'CONFIRMED' } });
    fireEvent.change(screen.getByLabelText('Invoice date from'), { target: { value: '2026-05-01' } });
    fireEvent.change(screen.getByLabelText('Invoice date before'), { target: { value: '2026-11-01' } });
    fireEvent.change(screen.getByLabelText('Collection'), { target: { value: 'true' } });
  });
  const expected = { customer_id: 'customer-a', status: 'CONFIRMED', from: '2026-05-01', to: '2026-11-01', overdue: 'true', page: '1' };
  await waitFor(() => expect(Object.fromEntries(query())).toEqual(expected));
  const lastApi = request.mock.calls.filter(([path]) => path.startsWith('/invoices?')).at(-1)?.[0];
  expect(Object.fromEntries(new URL(lastApi!, 'http://api.test').searchParams)).toEqual({ ...expected, page_size: '25' });
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Back' }));
  expect(Object.fromEntries(query())).toEqual({ customer_id: 'customer-a', status: 'CONFIRMED', from: '2026-05-01', to: '2026-11-01', page: '1' });
  expect(screen.getByLabelText('Customer')).toHaveValue('customer-a');
  expect(screen.getByLabelText('Collection')).toHaveValue('');
  await user.click(screen.getByRole('button', { name: 'Forward' }));
  expect(Object.fromEntries(query())).toEqual(expected);
  expect(screen.getByLabelText('Collection')).toHaveValue('true');
});

it('uses external drilldown and Back state as the base for the next rapid edit', async () => {
  setup();
  await screen.findByRole('option', { name: 'Customer A' });
  const user = userEvent.setup();
  await user.click(screen.getByRole('link', { name: 'Open another drilldown' }));
  expect(screen.getByLabelText('Customer')).toHaveValue('customer-b');
  act(() => {
    fireEvent.change(screen.getByLabelText('Collection'), { target: { value: 'false' } });
    fireEvent.change(screen.getByLabelText('Invoice date from'), { target: { value: '2026-06-01' } });
  });
  await waitFor(() => expect(Object.fromEntries(query())).toEqual({ customer_id: 'customer-b', status: 'PAID', overdue: 'false', from: '2026-06-01', page: '1' }));
  await user.click(screen.getByRole('button', { name: 'Back' }));
  fireEvent.change(screen.getByLabelText('Invoice status'), { target: { value: 'CONFIRMED' } });
  expect(Object.fromEntries(query())).toEqual({ customer_id: 'customer-b', status: 'CONFIRMED', overdue: 'false', page: '1' });
});
