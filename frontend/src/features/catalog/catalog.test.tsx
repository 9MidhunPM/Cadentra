import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../components/ui";
import { Products } from "./Products";
import { Plans } from "./Plans";
import { Customers } from "./Customers";

const state = vi.hoisted(() => ({ role: "ADMIN", request: vi.fn() }));
vi.mock("../../lib", () => ({
  apiClient: { request: state.request },
  useSession: () => ({ actor: { role: state.role } }),
  getErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  isAbortError: (error: unknown) =>
    error instanceof Error && error.name === "AbortError",
}));
const product = {
  id: "product-1",
  name: "Service",
  product_type: "SERVICE",
  sales_price: "12.30",
  cost_price: "2.50",
  notes: null,
  active: true,
};
const list = (items: unknown[] = []) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 25,
});
const mount = (element: React.ReactNode) =>
  render(<ToastProvider>{element}</ToastProvider>);
afterEach(cleanup);
beforeEach(() => {
  state.role = "ADMIN";
  state.request.mockReset();
});

describe("catalog workspaces", () => {
  it("saves product amounts as exact strings and refreshes persisted records", async () => {
    state.request.mockImplementation(async (_path, options) =>
      options?.method === "POST" ? { data: product } : list(),
    );
    mount(<Products />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "New product" }));
    await user.type(screen.getByLabelText("Product name"), "Service");
    await user.clear(screen.getByLabelText("Sales price (INR)"));
    await user.type(screen.getByLabelText("Sales price (INR)"), "12.30");
    await user.clear(screen.getByLabelText("Internal cost (INR)"));
    await user.type(screen.getByLabelText("Internal cost (INR)"), "2.50");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/products",
        expect.objectContaining({
          method: "POST",
          json: expect.objectContaining({
            sales_price: "12.30",
            cost_price: "2.50",
            name: "Service",
            active: true,
          }),
        }),
      ),
    );
    await screen.findByText("Product saved.");
  });
  it("shows staff the catalog without administrator mutation controls", async () => {
    state.role = "STAFF";
    state.request.mockResolvedValue(list([product]));
    mount(<Products />);
    await screen.findByText("Service");
    expect(
      screen.queryByRole("button", { name: "New product" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit Service" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Archive" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Variants for Service" }),
    ).toBeInTheDocument();
  });
  it("preserves the plan form and presents a rejected server write", async () => {
    state.request.mockImplementation(async (_path, options) => {
      if (options?.method === "POST") throw new Error("Availability conflict");
      return list();
    });
    mount(<Plans />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "New plan" }));
    await user.type(screen.getByLabelText("Plan name"), "Monthly service");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText("Availability conflict");
    expect(screen.getByLabelText("Plan name")).toHaveValue("Monthly service");
    expect(state.request).toHaveBeenCalledWith(
      "/plans",
      expect.objectContaining({
        json: expect.objectContaining({
          base_fee: "0.00",
          currency: "INR",
          cadence: "MONTHLY",
          min_quantity: 1,
          auto_close: true,
        }),
      }),
    );
  });
  it("sends customer search to the backend and keeps staff customer creation available", async () => {
    state.role = "STAFF";
    state.request.mockResolvedValue(list());
    mount(<Customers />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Search customers"), "Alice & Co");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/customers?page=1&page_size=25&q=Alice%20%26%20Co",
        expect.anything(),
      ),
    );
    expect(
      screen.getByRole("button", { name: "New customer" }),
    ).toBeInTheDocument();
  });
  it("saves a signed variant adjustment without converting it to floating point", async () => {
    state.request.mockImplementation(async (path, options) => {
      if (options?.method === "POST") return { data: { id: "variant-1" } };
      if (path === "/products/product-1")
        return { data: { ...product, variants: [] } };
      return list([product]);
    });
    mount(<Products />);
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Variants for Service" }),
    );
    await user.click(screen.getByRole("button", { name: "Add variant" }));
    await user.type(screen.getByLabelText("Attribute name"), "Tier");
    await user.type(screen.getByLabelText("Attribute value"), "Starter");
    await user.clear(screen.getByLabelText("Price adjustment (INR)"));
    await user.type(screen.getByLabelText("Price adjustment (INR)"), "-1.20");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/products/product-1/variants",
        expect.objectContaining({
          method: "POST",
          json: expect.objectContaining({
            price_delta: "-1.20",
            attribute_name: "Tier",
            attribute_value: "Starter",
          }),
        }),
      ),
    );
  });

  it("selects taxes by name and sends their identities without a raw-ID field", async () => {
    state.request.mockImplementation(async (path, options) => {
      if (options?.method === "POST") return { data: { id: "plan-1" } };
      if (path.startsWith("/tax-rules?"))
        return list([
          {
            id: "tax-18",
            name: "Standard service tax",
            rate_percent: "18.0000",
          },
        ]);
      return list();
    });
    mount(<Plans />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "New plan" }));
    await user.click(
      await screen.findByRole("checkbox", {
        name: "Standard service tax · 18.0000%",
      }),
    );
    expect(
      screen.queryByLabelText("Base-fee tax rule IDs"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("tax-18")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Plan name"), "Named taxes");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/plans",
        expect.objectContaining({
          json: expect.objectContaining({
            tax_rule_ids: ["tax-18"],
            base_fee: "0.00",
          }),
        }),
      ),
    );
  });
  it("retains saved taxes when the picker service is unavailable", async () => {
    const plan = {
      id: "plan-1",
      name: "Existing plan",
      base_fee: "100.00",
      currency: "INR",
      cadence: "MONTHLY",
      min_quantity: 1,
      available_from: "2026-01-01",
      available_until: null,
      allow_pause: false,
      allow_early_close: false,
      allow_renew: false,
      auto_close: true,
      tax_rule_ids: ["saved-not-on-page"],
    };
    state.request.mockImplementation(async (path, options) => {
      if (options?.method === "PATCH") return { data: plan };
      if (path.startsWith("/tax-rules?")) throw new Error("Unavailable");
      return list([plan]);
    });
    mount(<Plans />);
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Edit Existing plan" }),
    );
    await screen.findByText("Tax rules are unavailable");
    expect(
      screen.getByText("1 saved tax assignment is retained outside this page."),
    ).toBeInTheDocument();
    expect(screen.queryByText("saved-not-on-page")).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText("Plan name"));
    await user.type(screen.getByLabelText("Plan name"), "Edited plan");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/plans/plan-1",
        expect.objectContaining({
          method: "PATCH",
          json: expect.objectContaining({
            name: "Edited plan",
            tax_rule_ids: ["saved-not-on-page"],
          }),
        }),
      ),
    );
  });
  it("preserves selected taxes not present on the loaded picker page", async () => {
    const plan = {
      id: "plan-2",
      name: "Paged plan",
      base_fee: "0.00",
      currency: "INR",
      cadence: "MONTHLY",
      min_quantity: 1,
      available_from: "2026-01-01",
      available_until: null,
      allow_pause: false,
      allow_early_close: false,
      allow_renew: false,
      auto_close: true,
      tax_rule_ids: ["later-tax"],
    };
    state.request.mockImplementation(async (path, options) => {
      if (options?.method === "PATCH") return { data: plan };
      if (path.startsWith("/tax-rules?"))
        return {
          items: [
            { id: "current-tax", name: "Current rule", rate_percent: "5" },
          ],
          total: 30,
          page: 1,
          page_size: 25,
        };
      return list([plan]);
    });
    mount(<Plans />);
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Edit Paged plan" }),
    );
    await user.click(
      await screen.findByRole("checkbox", { name: "Current rule · 5%" }),
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(state.request).toHaveBeenCalledWith(
        "/plans/plan-2",
        expect.objectContaining({
          json: expect.objectContaining({
            tax_rule_ids: ["later-tax", "current-tax"],
          }),
        }),
      ),
    );
  });
  it("does not show a previous page under failed new-page pagination", async () => {
    state.request.mockImplementation(async (path) => {
      if (path.includes("page=2")) throw new Error("Page unavailable");
      return { ...list([product]), total: 50 };
    });
    mount(<Products />);
    const user = userEvent.setup();
    await screen.findByText("Service");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Page unavailable");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Service")).not.toBeInTheDocument();
  });
  it("clears failed query results while keeping an open customer editor intact", async () => {
    const customer = {
      id: "customer-1",
      display_name: "Alice Seed",
      email: "alice@example.com",
      company_name: null,
      billing_address: {},
    };
    state.request.mockImplementation(async (path) => {
      if (path.includes("&q=")) throw new Error("Search unavailable");
      return list([customer]);
    });
    mount(<Customers />);
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Edit Alice Seed" }),
    );
    await user.type(screen.getByLabelText("Search customers"), "Other name");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText("Search unavailable");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Customer name")).toHaveValue("Alice Seed");
  });
});
