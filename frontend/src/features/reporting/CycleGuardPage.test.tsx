import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CycleGuardPage } from "./CycleGuardPage";
const state = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib", () => ({
  apiClient: { request: state.request },
  getErrorMessage: (e: unknown) =>
    e instanceof Error ? e.message : "Request failed",
  isAbortError: (e: unknown) => e instanceof Error && e.name === "AbortError",
}));
vi.mock("./CustomerFilter", () => ({
  CustomerFilter: ({
    onChange,
  }: {
    onChange: (id: string, name: string) => void;
  }) => (
    <button onClick={() => onChange("customer-1", "Alice")}>
      Filter Alice
    </button>
  ),
}));
const empty = {
  items: [],
  total: 0,
  page: 1,
  page_size: 25,
  as_of: "2026-10-31",
};
const item = {
  id: "queue-1",
  kind: "OVERDUE",
  record_id: "invoice-1",
  record_type: "invoice",
  label: "INV-001",
  reason: "Balance remains after the due date.",
  occurred_on: "2026-10-01",
  amount: "4970.16",
  currency: "INR",
  attempts: null,
  next_attempt_at: null,
  error_code: null,
};
function mount(path = "/cycleguard") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CycleGuardPage />
    </MemoryRouter>,
  );
}
afterEach(cleanup);
beforeEach(() => {
  state.request.mockReset();
});
describe("CycleGuard read-only queue", () => {
  it("shows exact overdue balance and links to the source without a mutation", async () => {
    state.request.mockResolvedValue({ ...empty, items: [item], total: 1 });
    mount();
    const link = await screen.findByRole("link", { name: "INV-001" });
    expect(link).toHaveAttribute("href", "/billing/invoices/invoice-1");
    expect(screen.getByText("INR 4,970.16")).toBeInTheDocument();
    expect(
      screen.getByText("Balance remains after the due date."),
    ).toBeInTheDocument();
    expect(state.request).toHaveBeenCalledWith(
      "/reports/cycleguard?kind=OVERDUE&page=1&page_size=25",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(
      state.request.mock.calls.every(([, options]) => !options.method),
    ).toBe(true);
  });
  it("switches queues by keyboard, keeps customer scope and hides prior records on failure", async () => {
    state.request.mockImplementation(async (path: string) => {
      if (path.includes("BILLING_DUE"))
        throw new Error("Queue temporarily unavailable");
      return { ...empty, items: [item], total: 1 };
    });
    mount();
    const user = userEvent.setup();
    await screen.findByRole("link", { name: "INV-001" });
    await user.click(screen.getByRole("button", { name: "Filter Alice" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        expect.stringContaining("customer_id=customer-1"),
        expect.anything(),
      ),
    );
    const tab = screen.getByRole("tab", { name: "Overdue invoices" });
    tab.focus();
    await user.keyboard("{ArrowRight}");
    await screen.findByText("Queue temporarily unavailable");
    expect(
      screen.queryByRole("link", { name: "INV-001" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Billing due" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(state.request).toHaveBeenCalledWith(
      "/reports/cycleguard?kind=BILLING_DUE&page=1&page_size=25&customer_id=customer-1",
      expect.anything(),
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(state.request.mock.calls.length).toBeGreaterThanOrEqual(4);
  });
  it("shows failed-mail retry context without revealing the raw transport code", async () => {
    state.request.mockResolvedValue({
      ...empty,
      items: [
        {
          ...item,
          kind: "EMAIL_FAILED",
          amount: null,
          currency: null,
          attempts: 2,
          next_attempt_at: "2026-11-01T06:00:00Z",
          error_code: "SMTP_AUTH",
          reason: "Invoice email has a failed delivery attempt.",
        },
      ],
      total: 1,
    });
    mount("/cycleguard?kind=EMAIL_FAILED");
    await screen.findByText(/Mail provider authentication failed/);
    expect(screen.getByText(/Next retry eligible:/)).toBeInTheDocument();
    expect(
      screen.queryByText("SMTP_AUTH"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Not applicable")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /resend|run billing/i }),
    ).not.toBeInTheDocument();
  });
});
