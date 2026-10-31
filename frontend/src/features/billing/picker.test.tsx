/** Product-page fixtures verify picker behavior, not the live catalog query. */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient, ApiError } from '../../lib';
import { RulePage } from './rules';
import { setRuleWrite } from './ruleWrites';

vi.mock('../../lib', async importOriginal => ({
  ...await importOriginal<typeof import('../../lib')>(),
  useSession: () => ({ actor: { id: 'picker-admin', role: 'ADMIN', name: 'Administrator', customer_id: null } }),
}));
afterEach(() => {
  vi.restoreAllMocks();
  setRuleWrite('tax', 'idle');
  setRuleWrite('discount', 'idle');
});

const catalogue = Array.from({ length: 125 }, (_, index) => ({ id: `product-${index + 1}`, name: `Product ${index + 1}` }));
const emptyRules = { items: [], total: 0, page: 1, page_size: 25 };

describe('billing product selection', () => {
  it('reaches products beyond the first 100 and preserves names and IDs across search, pages and scope changes', async () => {
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
      if (options?.method === 'POST') return { data: { id: 'discount-created', effective_from: '2026-10-31' } };
      const url = new URL(path, 'http://api.test');
      if (url.pathname !== '/products') return emptyRules;
      const matches = catalogue.filter(product => product.name.includes(url.searchParams.get('q') ?? ''));
      const page = Number(url.searchParams.get('page'));
      return { items: matches.slice((page - 1) * 100, page * 100), total: matches.length, page, page_size: 100 };
    });
    render(<RulePage kind="discount" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Create discount rule' }));
    await user.type(screen.getByLabelText('Rule name'), 'Selected product discount');
    await user.type(screen.getByLabelText('Discount percentage'), '10');
    fireEvent.change(screen.getByLabelText('Eligibility starts on'), { target: { value: '2026-10-31' } });
    await user.selectOptions(screen.getByLabelText('Discount scope'), 'PRODUCTS');
    await user.click(await screen.findByRole('checkbox', { name: 'Product 1' }));
    await user.click(screen.getByRole('button', { name: 'Next products' }));
    expect(await screen.findByText('125 matching products · Page 2 of 2')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Product 125' }));
    expect(screen.getByRole('button', { name: 'Remove selected product Product 1' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search eligible products'), { target: { value: 'Product 125' } });
    expect(await screen.findByText('1 matching product · Page 1 of 1')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Product 125' })).toBeChecked();
    expect(request.mock.calls.some(([path]) => path === '/products?page=1&page_size=100&q=Product%20125')).toBe(true);
    expect(screen.getByRole('button', { name: 'Remove selected product Product 1' })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Discount scope'), 'SUBSCRIPTION');
    expect(screen.queryByLabelText('Search eligible products')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Discount scope'), 'PRODUCTS');
    expect(screen.getByRole('button', { name: 'Remove selected product Product 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove selected product Product 125' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    await waitFor(() => expect(request.mock.calls.find(([, options]) => options?.method === 'POST')?.[1]?.json).toMatchObject({
      scope: 'PRODUCTS', product_ids: ['product-1', 'product-125'],
    }));
  });

  it('resolves off-page and archived revision selection names without visiting their product pages', async () => {
    const rule = { id: 'tax-rule', name: 'Stored tax', rate_percent: '18.0000', active: true, effective_from: '2026-10-31', valid_from: '2026-10-31', product_ids: ['product-125', 'archived-product'] };
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
      if (options?.method === 'PATCH') return { data: { ...rule, effective_from: '2026-11-01' } };
      if (path === '/products/product-125') return { data: catalogue[124] };
      if (path === '/products/archived-product') return { data: { id: 'archived-product', name: 'Archived legacy product', active: false } };
      const url = new URL(path, 'http://api.test');
      if (url.pathname !== '/products') return { items: [rule], total: 1, page: 1, page_size: 25 };
      const page = Number(url.searchParams.get('page'));
      return { items: catalogue.slice((page - 1) * 100, page * 100), total: 125, page, page_size: 100 };
    });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Schedule revision' }));
    expect(await screen.findByRole('button', { name: 'Remove selected product Product 125' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Remove selected product Archived legacy product' })).toBeInTheDocument();
    expect(request.mock.calls.some(([path]) => path === '/products/product-125')).toBe(true);
    expect(request.mock.calls.some(([path]) => path === '/products/archived-product')).toBe(true);
    expect(request.mock.calls.filter(([path]) => path.startsWith('/products?')).every(([path]) => new URL(path, 'http://api.test').searchParams.get('page') === '1')).toBe(true);
    expect(screen.queryByRole('button', { name: 'Remove selected product product-125' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Remove selected product archived-product' })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Revision effective from'), { target: { value: '2026-11-01' } });
    const editor = screen.getByRole('heading', { name: 'Schedule a retained revision' }).closest('form');
    if (!editor) throw new Error('The retained revision editor is missing');
    await user.click(within(editor).getByRole('button', { name: 'Schedule revision' }));
    await waitFor(() => expect(request.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.json).toMatchObject({ product_ids: ['product-125', 'archived-product'] }));
  });

  it('does not advance past an unreadable product page and supports explicit retry', async () => {
    let loaded = false;
    let rejectLoad: (reason: unknown) => void = () => { throw new Error('The product request has not started'); };
    vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (!path.startsWith('/products?')) return emptyRules;
      if (!loaded) return new Promise((_resolve, reject) => { rejectLoad = reject; });
      return { items: [], total: 0, page: 1, page_size: 100 };
    });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Create tax rule' }));
    expect(screen.getByLabelText('Loading products')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next products' })).toBeDisabled();
    await act(async () => rejectLoad(new ApiError(503, 'UNAVAILABLE', 'Catalogue temporarily unavailable.')));
    expect(await screen.findByRole('alert')).toHaveTextContent('Catalogue temporarily unavailable.');
    expect(screen.getByRole('button', { name: 'Previous products' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next products' })).toBeDisabled();
    loaded = true;
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No matching products. Search another name.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next products' })).toBeDisabled();
  });
  it('keeps retained IDs through detail loading and failure, then resolves the human label only after explicit retry', async () => {
    const retainedId = 'archived-off-page-id';
    const rule = { id: 'tax-with-detail', name: 'Stored membership', rate_percent: '18.0000', active: true, effective_from: '2026-10-31', valid_from: '2026-10-31', product_ids: [retainedId] };
    let attempts = 0;
    let rejectDetail: (error: unknown) => void = () => { throw new Error('Detail request not started'); };
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
      if (options?.method === 'PATCH') return { data: { ...rule, effective_from: '2026-11-01' } };
      if (path === `/products/${retainedId}`) {
        attempts += 1;
        if (attempts === 1) return new Promise((_resolve, reject) => { rejectDetail = reject; });
        return { data: { id: retainedId, name: 'Archived recovered product', active: false } };
      }
      if (path.startsWith('/products?')) return { items: catalogue.slice(0, 100), total: 125, page: 1, page_size: 100 };
      return { items: [rule], total: 1, page: 1, page_size: 25 };
    });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Schedule revision' }));
    const unresolved = await screen.findByRole('group', { name: 'Selected product 1' });
    expect(within(unresolved).getByRole('status')).toHaveTextContent('Loading selected product name');
    expect(unresolved).not.toHaveTextContent(retainedId);
    expect(within(unresolved).getByRole('button', { name: 'Remove selected product' })).toBeEnabled();
    await act(async () => rejectDetail(new ApiError(503, 'UNAVAILABLE', 'Catalogue detail temporarily unavailable.')));
    expect(await screen.findByRole('alert')).toHaveTextContent('Selected product name unavailable.');
    expect(screen.getByRole('alert')).toHaveTextContent('Catalogue detail temporarily unavailable.');
    expect(attempts).toBe(1);
    expect(screen.getByRole('group', { name: 'Selected product 1' })).not.toHaveTextContent(retainedId);
    await user.click(screen.getByRole('button', { name: 'Retry product name' }));
    expect(await screen.findByRole('button', { name: 'Remove selected product Archived recovered product' })).toBeInTheDocument();
    expect(attempts).toBe(2);
    fireEvent.change(screen.getByLabelText('Revision effective from'), { target: { value: '2026-11-01' } });
    const editor = screen.getByRole('heading', { name: 'Schedule a retained revision' }).closest('form');
    if (!editor) throw new Error('Revision form missing');
    await user.click(within(editor).getByRole('button', { name: 'Schedule revision' }));
    await waitFor(() => expect(request.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.json).toMatchObject({ product_ids: [retainedId] }));
  });

  it('does not resurrect a removed retained selection when its pending detail lookup completes', async () => {
    const retainedId = 'pending-selected-id';
    const rule = { id: 'tax-with-pending-detail', name: 'Stored membership', rate_percent: '18.0000', active: true, effective_from: '2026-10-31', valid_from: '2026-10-31', product_ids: [retainedId] };
    let finishDetail: (value: unknown) => void = () => { throw new Error('Detail request not started'); };
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
      if (options?.method === 'PATCH') return { data: { ...rule, effective_from: '2026-11-01' } };
      if (path === `/products/${retainedId}`) return new Promise(resolve => { finishDetail = resolve; });
      if (path.startsWith('/products?')) return { items: catalogue.slice(0, 100), total: 125, page: 1, page_size: 100 };
      return { items: [rule], total: 1, page: 1, page_size: 25 };
    });
    render(<RulePage kind="tax" />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Schedule revision' }));
    const unresolved = await screen.findByRole('group', { name: 'Selected product 1' });
    expect(within(unresolved).getByRole('status')).toHaveTextContent('Loading selected product name');
    await user.click(within(unresolved).getByRole('button', { name: 'Remove selected product' }));
    await act(async () => finishDetail({ data: { id: retainedId, name: 'Late product label', active: false } }));
    expect(screen.queryByRole('group', { name: /Selected product/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Late product label')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Revision effective from'), { target: { value: '2026-11-01' } });
    const editor = screen.getByRole('heading', { name: 'Schedule a retained revision' }).closest('form');
    if (!editor) throw new Error('Revision form missing');
    await user.click(within(editor).getByRole('button', { name: 'Schedule revision' }));
    await waitFor(() => expect(request.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1]?.json).toMatchObject({ product_ids: [] }));
  });

});
