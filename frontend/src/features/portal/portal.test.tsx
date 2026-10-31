import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "../../lib";
import { getRoutes } from "./index";

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
  plan_snapshot: { name: "Workspace plan" },
  lines: [
    {
      id: "line",
      description: "Software seats",
      quantity: 3,
      unit_price: "1560.00",
    },
  ],
  invoices: [],
};
function open(path: string) {
  const router = createMemoryRouter(getRoutes(), { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}
afterEach(() => vi.restoreAllMocks());

describe("customer portal", () => {
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
    await userEvent.click(
      await screen.findByRole("button", { name: "Pause subscription" }),
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
          state: "DRAFT",
        },
      })
      .mockResolvedValue({
        data: { ...subscription, id: "renewal", state: "DRAFT" },
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
      await screen.findByText(/Your renewal draft was created/),
    ).toBeVisible();
    expect(request).toHaveBeenCalledWith(
      "/portal/subscriptions/own-sub/renew",
      {
        method: "POST",
        json: { start_date: "2026-12-01", end_date: "2027-01-01" },
      },
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
