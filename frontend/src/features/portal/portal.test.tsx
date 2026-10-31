import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "../../lib";
import { getRoutes } from "./index";
import type { InvoiceDetail, SubscriptionDetail } from "./types";

// Client fixtures only; PostgreSQL tests establish backend ownership enforcement.
const subscription = {
  id: "own-sub",
  number: "SUB-42",
  plan_id: "plan",
  state: "ACTIVE",
  start_date: "2026-10-01",
  end_date: "2026-12-01",
  currency: "INR",
  close_effective_on: null,
  revision: 1,
  payment_terms_days: 7,
  prior_subscription_id: null,
  expired: false,
  recurring_subtotal: "5100.50",
  recurring_subtotal_basis: "before tax and discounts",
  base_fee_taxes: [
    { id: "base-tax", name: "Plan tax", rate_percent: "5.0000" },
  ],
  tax_preview_on: "2026-11-01",
  tax_preview_basis:
    "Applicable rules at this service-period start; invoice snapshots determine final taxes",
  paused: false,
  pause_interval: null,
  pause_effective_on: null,
  resume_effective_on: null,
  plan_snapshot: { name: "Workspace plan" },
  lines: [
    {
      id: "line",
      description: "Software seats",
      quantity: 3,
      unit_price: "1560.00",
      line_total: "4680.00",
      taxes: [
        { id: "product-tax", name: "Product tax", rate_percent: "18.0000" },
      ],
    },
  ],
  invoice_references: [
    { id: "linked-invoice", number: "INV-41", status: "PAID" },
  ],
} satisfies SubscriptionDetail;

const invoiceDetail = {
  id: "own-invoice",
  number: "INV-00000008",
  subscription_id: subscription.id,
  status: "CONFIRMED",
  collection_status: "PARTIALLY_PAID",
  currency: "INR",
  invoice_date: "2026-10-01",
  due_date: "2026-10-08",
  period_start: "2026-10-01",
  period_end: "2026-11-01",
  subtotal: "100.00",
  discount_total: "0.00",
  tax_total: "0.00",
  total: "100.00",
  paid_amount: "26.79",
  balance_due: "73.21",
  overdue: true,
  lines: [],
  payments: [
    { id: "payment", method: "MANUAL", amount: "26.79", paid_on: "2026-10-03" },
  ],
} satisfies InvoiceDetail;

function open(path: string) {
  const router = createMemoryRouter(getRoutes(), { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}
afterEach(() => vi.restoreAllMocks());

describe("customer portal", () => {
  it.each(["subscriptions", "invoices"])(
    "shows an honest empty %s list without a fabricated page count",
    async (kind) => {
      vi.spyOn(apiClient, "request").mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 25,
      });
      open(`/portal/${kind}`);
      expect(
        await screen.findByRole("heading", { name: `No ${kind} yet` }),
      ).toBeVisible();
      expect(
        screen.getByText(`0 ${kind} in total. No records on page 1.`),
      ).toBeVisible();
      expect(screen.queryByText(/Page 1 of 1/)).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Back to first page" }),
      ).not.toBeInTheDocument();
    },
  );

  it.each([
    { kind: "subscriptions", total: 1, row: subscription, singular: "subscription" },
    { kind: "invoices", total: 1, row: invoiceDetail, singular: "invoice" },
    { kind: "subscriptions", total: 0, row: subscription, singular: "subscription" },
    { kind: "invoices", total: 0, row: invoiceDetail, singular: "invoice" },
  ])(
    "recovers an empty $kind page when the server total is $total",
    async ({ kind, total, row, singular }) => {
      const request = vi.spyOn(apiClient, "request")
        .mockResolvedValueOnce({ items: [], total, page: 99, page_size: 25 })
        .mockResolvedValueOnce({
          items: total ? [row] : [],
          total,
          page: 1,
          page_size: 25,
        });
      const router = open(`/portal/${kind}?page=99`);
      expect(
        await screen.findByRole("heading", { name: `No ${kind} on this page` }),
      ).toBeVisible();
      expect(
        screen.getByText(`${total} ${total === 1 ? singular : kind} in total. No records on page 99.`),
      ).toBeVisible();
      expect(screen.queryByText(/Page 99 of/)).not.toBeInTheDocument();
      await userEvent.click(
        screen.getByRole("button", { name: "Back to first page" }),
      );
      await waitFor(() => expect(router.state.location.search).toBe("?page=1"));
      if (total) {
        expect(await screen.findByRole("link", { name: row.number })).toBeVisible();
      } else {
        expect(
          await screen.findByRole("heading", { name: `No ${kind} yet` }),
        ).toBeVisible();
      }
      expect(request).toHaveBeenLastCalledWith(
        `/portal/${kind}?page=1&page_size=25`,
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      );
    },
  );

  it.each([
    { status: "CONFIRMED", label: "Remaining balance", balance: "73.21", paid: "26.79" },
    { status: "PAID", label: "Remaining balance", balance: "0.00", paid: "100.00" },
    { status: "DRAFT", label: "Document balance", balance: "100.00", paid: "0.00" },
    { status: "CANCELLED", label: "Document balance", balance: "100.00", paid: "0.00" },
  ])(
    "puts the stored $status balance next to the invoice identity",
    async ({ status, label, balance, paid }) => {
      vi.spyOn(apiClient, "request").mockResolvedValue({ data: {
        ...invoiceDetail,
        status,
        collection_status: status,
        balance_due: balance,
        paid_amount: paid,
      } });
      open(`/portal/invoices/${invoiceDetail.id}`);
      const number = await screen.findByRole("heading", { name: invoiceDetail.number });
      const summary = screen.getByLabelText("Invoice balance summary");
      expect(number.closest(".portal-invoice-heading")).toContainElement(summary);
      expect(within(summary).getByText(label)).toBeVisible();
      expect(within(summary).getByText(`INR ${balance}`)).toBeVisible();
      if (["DRAFT", "CANCELLED"].includes(status)) {
        expect(within(summary).getByText("Not payable")).toBeVisible();
      }
    },
  );

  it("names the invoice line and payment scrollers and makes them keyboard focusable", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValue({ data: invoiceDetail });
    open(`/portal/invoices/${invoiceDetail.id}`);
    for (const name of ["Stored invoice lines", "Recorded payments"]) {
      const region = await screen.findByRole("region", { name });
      expect(region).toHaveAttribute("tabindex", "0");
      region.focus();
      expect(region).toHaveFocus();
      expect(within(region).getByRole("table")).toBeVisible();
    }
  });

  it("keeps subscription lines in a named keyboard-focusable scroller", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValue({ data: subscription });
    open(`/portal/subscriptions/${subscription.id}`);
    const region = await screen.findByRole("region", { name: "Agreed product lines" });
    expect(region).toHaveAttribute("tabindex", "0");
    region.focus();
    expect(region).toHaveFocus();
  });

  it("shows recorded balances without collecting online payment or selecting a customer", async () => {
    const request = vi.spyOn(apiClient, "request").mockResolvedValue({
      items: [
        {
          id: "invoice",
          number: "INV-42",
          subscription_id: "own-sub",
          status: "CONFIRMED",
          collection_status: "PARTIALLY_PAID",
          currency: "INR",
          invoice_date: "2026-10-01",
          due_date: "2026-10-08",
          period_start: "2026-10-01",
          period_end: "2026-11-01",
          total: "4970.16",
          paid_amount: "2000.00",
          balance_due: "2970.16",
          overdue: true,
        },
      ],
      total: 1,
      page: 1,
      page_size: 25,
    });
    open("/portal/invoices");
    expect(await screen.findByRole("link", { name: "INV-42" })).toHaveAttribute(
      "href",
      "/portal/invoices/invoice",
    );
    expect(screen.getByText("INR 2,970.16")).toBeVisible();
    expect(screen.getByText("Partially paid")).toBeVisible();
    expect(screen.getByText("Overdue")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /pay now/i }),
    ).not.toBeInTheDocument();
    expect(request.mock.calls[0][0]).not.toContain("customer_id");
    expect(screen.getByRole("region", { name: "My invoices" })).toHaveAttribute(
      "tabindex", "0",
    );
  });

  it("retains honest missing-record errors and retries explicitly", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockRejectedValueOnce(
        new ApiError(404, "NOT_FOUND", "Record not found."),
      )
      .mockResolvedValueOnce({ data: subscription });
    open("/portal/subscriptions/own-sub");
    expect(await screen.findByText("Record unavailable")).toBeVisible();
    expect(screen.queryByText("Workspace plan")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "Workspace plan" }),
    ).toBeVisible();
    expect(request).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByRole("button", { name: "Pause subscription" }),
    ).not.toBeInTheDocument();
  });

  it("only exposes allowed actions and preserves a safe conflict explanation", async () => {
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["pause"] },
      })
      .mockRejectedValueOnce(
        new ApiError(
          409,
          "DUE_BILLING_PENDING",
          "Process due billing before changing the schedule.",
        ),
      );
    open("/portal/subscriptions/own-sub");
    await screen.findByRole("button", { name: "Pause subscription" });
    await userEvent.type(
      screen.getByLabelText("Reason (optional)"),
      "Keep my entered reason",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Pause subscription" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm pause" }),
    );
    expect(
      await screen.findByText(
        "Process due billing before changing the schedule.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("dialog")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByLabelText("Reason (optional)")).toHaveValue(
      "Keep my entered reason",
    );
    expect(
      screen.getByRole("button", { name: "Pause subscription" }),
    ).toHaveFocus();
    expect(
      screen.queryByRole("button", { name: "Close subscription" }),
    ).not.toBeInTheDocument();
  });

  it("creates a linked renewal draft with explicit dates and staff-review feedback", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["renew"] },
      })
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          id: "renewal",
          number: "SUB-43",
          prior_subscription_id: "own-sub",
          state: "DRAFT",
        },
      })
      .mockResolvedValue({
        data: {
          ...subscription,
          id: "renewal",
          prior_subscription_id: "own-sub",
          state: "DRAFT",
        },
      });
    const router = open("/portal/subscriptions/own-sub");
    await screen.findByRole("heading", { name: "Renew your subscription" });
    await userEvent.type(
      screen.getByLabelText("Renewal start date"),
      "2026-12-01",
    );
    await userEvent.type(
      screen.getByLabelText("Renewal ends before"),
      "2027-01-01",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create renewal draft" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /^Create draft$/ }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/portal/subscriptions/renewal",
      ),
    );
    expect(
      await screen.findByText(/Your linked renewal draft was created/),
    ).toBeVisible();
    expect(
      await screen.findByRole("link", { name: "View previous subscription" }),
    ).toHaveAttribute("href", "/portal/subscriptions/own-sub");
    expect(
      within(screen.getByRole("list", { name: "Subscription lifecycle" }))
        .getByText("Draft")
        .closest("li"),
    ).toHaveAttribute("aria-current", "step");
    expect(request).toHaveBeenCalledWith(
      "/portal/subscriptions/own-sub/renew",
      {
        method: "POST",
        json: { start_date: "2026-12-01", end_date: "2027-01-01" },
      },
    );
  });

  it("renders owner-shaped stored amounts, tax metadata, invoice references and effective dates", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValue({
      data: {
        ...subscription,
        paused: true,
        pause_interval: { starts_on: "2026-10-01", ends_on: "2026-11-01" },
        resume_effective_on: "2026-11-01",
        close_effective_on: "2026-12-01",
      },
    });
    open("/portal/subscriptions/own-sub");
    expect(
      await screen.findByRole("heading", { name: "Current pause" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /INV-41/ })).toHaveAttribute(
      "href",
      "/portal/invoices/linked-invoice",
    );
    expect(screen.getByText("INR 5,100.50")).toBeVisible();
    expect(screen.getByText("INR 4,680.00")).toBeVisible();
    expect(screen.getByText("before tax and discounts")).toBeVisible();
    expect(screen.getByText("Plan tax (5.0000%)")).toBeVisible();
    expect(screen.getByText("Product tax (18.0000%)")).toBeVisible();
    expect(
      screen
        .getByText("Service resumes")
        .nextElementSibling?.querySelector("time"),
    ).toHaveAttribute("dateTime", "2026-11-01");
    expect(
      screen
        .getByText("Closure takes effect")
        .nextElementSibling?.querySelector("time"),
    ).toHaveAttribute("dateTime", "2026-12-01");
  });

  it("applies a pause DTO without a refetch and focuses its stable effective-date notice after its trigger disappears", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["pause"] },
      })
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          revision: 2,
          allowed_actions: ["resume"],
          pause_interval: { starts_on: "2026-11-01", ends_on: null },
          pause_effective_on: "2026-11-01",
        },
      });
    open("/portal/subscriptions/own-sub");
    await userEvent.click(
      await screen.findByRole("button", { name: "Pause subscription" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm pause" }),
    );
    const notice = screen.getByRole("status");
    await waitFor(() => expect(notice).toHaveFocus());
    expect(within(notice).getByText(/Pause scheduled for/)).toBeVisible();
    expect(notice.querySelector("time")).toHaveAttribute(
      "dateTime",
      "2026-11-01",
    );
    expect(
      screen.getByRole("button", { name: "Cancel scheduled pause" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Pause subscription" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("No resume date scheduled")).toBeVisible();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("announces an immediate pause using the returned interval start", async () => {
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["pause"] },
      })
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          paused: true,
          pause_interval: { starts_on: "2026-10-31", ends_on: null },
          allowed_actions: [],
        },
      });
    open("/portal/subscriptions/own-sub");
    await userEvent.click(
      await screen.findByRole("button", { name: "Pause subscription" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm pause" }),
    );
    await waitFor(() => expect(screen.getByRole("status")).toHaveFocus());
    expect(screen.getByRole("status")).toHaveTextContent("Service paused from");
    expect(screen.getByRole("status").querySelector("time")).toHaveAttribute(
      "dateTime",
      "2026-10-31",
    );
  });

  it("cancels a scheduled pause through resume and announces the returned schedule", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          allowed_actions: ["resume"],
          pause_interval: { starts_on: "2026-11-01", ends_on: null },
          pause_effective_on: "2026-11-01",
        },
      })
      .mockResolvedValueOnce({
        data: { ...subscription, revision: 2, allowed_actions: ["pause"] },
      });
    open("/portal/subscriptions/own-sub");
    await userEvent.click(
      await screen.findByRole("button", { name: "Cancel scheduled pause" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Cancel scheduled pause",
      }),
    );
    expect(
      await screen.findByText("Your scheduled pause was cancelled."),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Scheduled pause" }),
    ).not.toBeInTheDocument();
    expect(request).toHaveBeenLastCalledWith(
      "/portal/subscriptions/own-sub/resume",
      { method: "POST", json: {} },
    );
  });

  it("announces a resume boundary from the returned DTO without changing the lifecycle state", async () => {
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          paused: true,
          pause_interval: { starts_on: "2026-10-01", ends_on: null },
          allowed_actions: ["resume"],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          paused: true,
          pause_interval: { starts_on: "2026-10-01", ends_on: "2026-11-01" },
          resume_effective_on: "2026-11-01",
          allowed_actions: [],
        },
      });
    open("/portal/subscriptions/own-sub");
    await userEvent.click(
      await screen.findByRole("button", { name: "Resume subscription" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm resume" }),
    );
    await waitFor(() => expect(screen.getByRole("status")).toHaveFocus());
    expect(screen.getByRole("status")).toHaveTextContent("Service resumes on");
    expect(screen.getByRole("status").querySelector("time")).toHaveAttribute(
      "dateTime",
      "2026-11-01",
    );
    expect(
      within(screen.getByRole("list", { name: "Subscription lifecycle" }))
        .getByText("Active")
        .closest("li"),
    ).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Paused")).toBeVisible();
  });

  it.each(["pause", "renew"])(
    "ignores a late %s response after navigation",
    async (action) => {
      let finish: (value: unknown) => void = () => {};
      const lateResponse = new Promise((resolve) => {
        finish = resolve;
      });
      const request = vi
        .spyOn(apiClient, "request")
        .mockResolvedValueOnce({
          data: { ...subscription, allowed_actions: [action] },
        })
        .mockImplementationOnce(() => lateResponse)
        .mockResolvedValue({
          data: {
            ...subscription,
            id: "other-sub",
            number: "SUB-OTHER",
            plan_snapshot: { name: "Other service" },
          },
        });
      const router = open("/portal/subscriptions/own-sub");
      if (action === "renew") {
        await screen.findByRole("heading", { name: "Renew your subscription" });
        await userEvent.type(
          screen.getByLabelText("Renewal start date"),
          "2026-12-01",
        );
        await userEvent.type(
          screen.getByLabelText("Renewal ends before"),
          "2027-01-01",
        );
        await userEvent.click(
          screen.getByRole("button", { name: "Create renewal draft" }),
        );
        await userEvent.click(
          screen.getByRole("button", { name: "Create draft" }),
        );
      } else {
        await userEvent.click(
          await screen.findByRole("button", { name: "Pause subscription" }),
        );
        await userEvent.click(
          screen.getByRole("button", { name: "Confirm pause" }),
        );
      }
      await act(() => router.navigate("/portal/subscriptions/other-sub"));
      await screen.findByRole("heading", { name: "Other service" });
      await act(async () => {
        finish({
          data: { ...subscription, id: "late-renewal", state: "DRAFT" },
        });
        await lateResponse;
      });
      expect(router.state.location.pathname).toBe(
        "/portal/subscriptions/other-sub",
      );
      expect(
        screen.getByRole("heading", { name: "Other service" }),
      ).toBeVisible();
      expect(screen.getByRole("status")).toBeEmptyDOMElement();
      expect(request).toHaveBeenCalledTimes(3);
    },
  );

  it("retains renewal dates after a rejected action and allows an explicit retry", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["renew"] },
      })
      .mockRejectedValueOnce(
        new ApiError(
          409,
          "RENEWAL_OVERLAP",
          "The requested renewal overlaps an existing term.",
        ),
      );
    const router = open("/portal/subscriptions/own-sub");
    await screen.findByRole("heading", { name: "Renew your subscription" });
    await userEvent.type(
      screen.getByLabelText("Renewal start date"),
      "2026-12-01",
    );
    await userEvent.type(
      screen.getByLabelText("Renewal ends before"),
      "2027-01-01",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create renewal draft" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Create draft" }));
    expect(
      await screen.findByText(
        "The requested renewal overlaps an existing term.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("dialog")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByLabelText("Renewal start date")).toHaveValue(
      "2026-12-01",
    );
    expect(screen.getByLabelText("Renewal ends before")).toHaveValue(
      "2027-01-01",
    );
    expect(
      screen.getByRole("button", { name: "Create renewal draft" }),
    ).toHaveFocus();
    expect(router.state.location.pathname).toBe(
      "/portal/subscriptions/own-sub",
    );
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("announces the server closure date and removes unavailable controls", async () => {
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["close"] },
      })
      .mockResolvedValueOnce({
        data: {
          ...subscription,
          close_effective_on: "2026-11-01",
          allowed_actions: [],
        },
      });
    open("/portal/subscriptions/own-sub");
    await userEvent.click(
      await screen.findByRole("button", { name: "Close subscription" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm close" }),
    );
    await waitFor(() => expect(screen.getByRole("status")).toHaveFocus());
    expect(screen.getByRole("status")).toHaveTextContent(
      "Closure takes effect on",
    );
    expect(screen.getByRole("status").querySelector("time")).toHaveAttribute(
      "dateTime",
      "2026-11-01",
    );
    expect(
      screen.queryByRole("heading", { name: "Manage your service" }),
    ).not.toBeInTheDocument();
  });

  it("ignores a late renewal response after the portal is unmounted", async () => {
    let finish: (value: unknown) => void = () => {};
    const lateResponse = new Promise((resolve) => {
      finish = resolve;
    });
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({
        data: { ...subscription, allowed_actions: ["renew"] },
      })
      .mockImplementationOnce(() => lateResponse);
    const router = createMemoryRouter(getRoutes(), {
      initialEntries: ["/portal/subscriptions/own-sub"],
    });
    const view = render(<RouterProvider router={router} />);
    await screen.findByRole("heading", { name: "Renew your subscription" });
    await userEvent.type(
      screen.getByLabelText("Renewal start date"),
      "2026-12-01",
    );
    await userEvent.type(
      screen.getByLabelText("Renewal ends before"),
      "2027-01-01",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create renewal draft" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Create draft" }));
    view.unmount();
    await act(async () => {
      finish({ data: { ...subscription, id: "late-renewal", state: "DRAFT" } });
      await lateResponse;
    });
    expect(router.state.location.pathname).toBe(
      "/portal/subscriptions/own-sub",
    );
  });

  it("prints through the authenticated portal route and omits staff-only payment notes", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValue({
      data: {
        id: "invoice",
        number: "INV-42",
        status: "CONFIRMED",
        collection_status: "PARTIALLY_PAID",
        currency: "INR",
        invoice_date: "2026-10-01",
        due_date: "2026-10-08",
        period_start: "2026-10-01",
        period_end: "2026-11-01",
        total: "4970.16",
        subtotal: "4680.00",
        discount_total: "468.00",
        tax_total: "758.16",
        paid_amount: "2000.00",
        balance_due: "2970.16",
        overdue: true,
        seller_snapshot: {
          name: "Brightloop Software",
          address: "Demo Avenue",
        },
        customer_snapshot: {
          display_name: "Own customer",
          email: "own@example.invalid",
          billing_address: {
            city: "Demo City",
            internal_notes: "PRIVATE ADDRESS NOTE",
          },
        },
        lines: [
          {
            id: "line",
            stable_line_key: "L1",
            description: "Stored software line",
            quantity: 3,
            unit_price: "1560.00",
            gross: "4680.00",
            discount: "468.00",
            taxable_amount: "4212.00",
            tax_total: "758.16",
            total: "4970.16",
            taxes: [
              {
                name: "Illustrative tax",
                rate_percent: "18.0000",
                amount: "758.16",
              },
            ],
          },
        ],
        payments: [
          {
            id: "payment",
            method: "BANK_TRANSFER",
            amount: "2000.00",
            paid_on: "2026-10-03",
            note: "PRIVATE STAFF NOTE",
          },
        ],
      },
    });
    open("/portal/invoices/invoice");
    const print = await screen.findByRole("link", { name: "Print invoice" });
    expect(print).toHaveAttribute(
      "href",
      "/api/v1/portal/invoices/invoice/print",
    );
    expect(print).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByText("PRIVATE STAFF NOTE")).not.toBeInTheDocument();
    expect(screen.queryByText("PRIVATE ADDRESS NOTE")).not.toBeInTheDocument();
    expect(screen.getByText("Demo City")).toBeVisible();
    expect(screen.getByText("Demo Avenue")).toBeVisible();
    expect(
      screen.getByRole("columnheader", { name: "Discount" }),
    ).toBeVisible();
    expect(screen.getByText("Stored software line")).toBeVisible();
    expect(screen.getAllByText("INR 758.16").length).toBeGreaterThan(0);
  });
});
