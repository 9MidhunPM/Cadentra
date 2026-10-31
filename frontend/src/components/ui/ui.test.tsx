import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../lib/api';
import { Button, ConfirmDialog, DataTable, DateLabel, FormField, Money, SubscriptionStepper, ToastProvider, useToast } from './index';

describe('shared controls', () => {
  it('formats decimal money without precision loss above Number.MAX_SAFE_INTEGER', () => {
    render(<Money amount="9007199254740993.01" currency="USD" />);
    expect(screen.getByText('USD 9,007,199,254,740,993.01')).toBeInTheDocument();
  });
  it('keeps INR explicit and canonical cents intact', () => {
    render(<Money amount="4970.16" />);
    expect(screen.getByText('INR 4,970.16')).toBeInTheDocument();
  });
  it('does not silently round an invalid money input', () => {
    render(<Money amount="1.999" />);
    expect(screen.getByLabelText('Amount unavailable')).toHaveTextContent('—');
  });
  it('renders service dates independently of local timezone and rejects impossible dates', () => {
    const { rerender } = render(<DateLabel value="2026-10-31" />);
    expect(screen.getByText('31 Oct 2026')).toHaveAttribute('datetime', '2026-10-31');
    rerender(<DateLabel value="2026-02-31" />);
    expect(screen.getByLabelText('Date unavailable')).toBeInTheDocument();
  });
  it('associates form labels, hints, and validation errors while preserving values', () => {
    render(<FormField id="email" label="Email" hint="Use your registered email" error="Check your email"><input defaultValue="still-here" aria-describedby="other-help" /></FormField>);
    const field = screen.getByLabelText('Email');
    expect(field).toHaveValue('still-here');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(field).toHaveAttribute('aria-describedby', 'other-help email-hint email-error');
    expect(screen.getByRole('alert')).toHaveTextContent('Check your email');
  });
  it('blocks duplicate pending button submissions', async () => {
    const onClick = vi.fn();
    render(<Button pending onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });
  it('uses server pagination and accessible empty state', async () => {
    const onPageChange = vi.fn();
    const { rerender } = render(<DataTable columns={[{ key: 'name', header: 'Name', render: (row: {id: string}) => row.id }]} rows={[{id:'a'}]} getRowKey={row => row.id} total={30} page={1} pageSize={25} onPageChange={onPageChange} />);
    expect(screen.getByRole('button', {name:'Previous'})).toBeDisabled();
    await userEvent.click(screen.getByRole('button', {name:'Next'}));
    expect(onPageChange).toHaveBeenCalledWith(2);
    rerender(<DataTable columns={[]} rows={[]} getRowKey={() => ''} total={0} page={1} pageSize={25} onPageChange={onPageChange} emptyTitle="No invoices" />);
    expect(screen.getByRole('heading', {name:'No invoices'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name:'Next'})).toBeDisabled();
  });
  it('marks the current lifecycle step using text and aria-current', () => {
    render(<SubscriptionStepper state="ACTIVE" />);
    expect(screen.getByText('Active').closest('li')).toHaveAttribute('aria-current', 'step');
  });
});

describe('confirmation dialog', () => {
  it('focuses cancel, blocks closing/repeats while pending, and restores trigger focus on success', async () => {
    let finish!: () => void;
    const onConfirm = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    render(<ConfirmDialog trigger={<Button>Close subscription</Button>} title="Schedule closure?" description="This takes effect at the next cycle." onConfirm={onConfirm} />);
    const trigger = screen.getByRole('button', {name:'Close subscription'});
    await userEvent.click(trigger);
    expect(screen.getByRole('button', {name:'Cancel'})).toHaveFocus();
    await userEvent.click(screen.getByRole('button', {name:'Confirm'}));
    expect(screen.getByRole('button', {name:'Confirm'})).toBeDisabled();
    expect(screen.getByRole('button', {name:'Cancel'})).toBeDisabled();
    await userEvent.keyboard('{Escape}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await act(async () => finish());
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });
  it('preserves safe domain errors so users understand why an action was rejected', async () => {
    const onConfirm = vi.fn().mockRejectedValue(new ApiError(409, 'INVALID_TRANSITION', 'Only active subscriptions can be paused.'));
    render(<ConfirmDialog title="Pause subscription" description="Pause from the next cycle." onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole('button', {name:'Continue'}));
    await userEvent.click(screen.getByRole('button', {name:'Confirm'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Only active subscriptions can be paused.');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', {name:'Cancel'})).toBeEnabled();
  });
  it('keeps a failed action open, permits retry, and does not expose raw errors', async () => {
    const onConfirm = vi.fn().mockRejectedValueOnce(new Error('private details')).mockResolvedValueOnce(undefined);
    render(<ConfirmDialog title="Confirm action" description="Review this change." onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole('button', {name:'Continue'}));
    await userEvent.click(screen.getByRole('button', {name:'Confirm'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Please try again.');
    expect(screen.queryByText('private details')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', {name:'Confirm'}));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onConfirm).toHaveBeenCalledTimes(2);
  });
});

it('announces and dismisses notifications without automatic time pressure', async () => {
  function Example() { const { toast } = useToast(); return <Button onClick={() => toast('Saved', 'success')}>Notify</Button>; }
  render(<ToastProvider><Example /></ToastProvider>);
  fireEvent.click(screen.getByRole('button', {name:'Notify'}));
  expect(screen.getByRole('status')).toHaveTextContent('Saved');
  await userEvent.click(screen.getByRole('button', {name:'Dismiss notification'}));
  expect(screen.queryByText('Saved')).not.toBeInTheDocument();
});
