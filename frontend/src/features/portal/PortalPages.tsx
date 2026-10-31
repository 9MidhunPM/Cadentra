import { useRef, useState, type ReactNode, type RefObject } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";
import { ArrowLeft, ArrowUpRight, FileText, Printer } from "lucide-react";
import {
  apiClient,
  ApiError,
  getErrorMessage,
  type ListResponse,
  type ResourceResponse,
} from "../../lib";
import {
  Button,
  ConfirmDialog,
  DataTable,
  DateLabel,
  EmptyState,
  ErrorPanel,
  FormField,
  LoadingSkeleton,
  Money,
  PageHeader,
  StatusBadge,
  SubscriptionStepper,
} from "../../components/ui";
import { usePortalResource } from "./usePortalResource";
import type {
  CustomerProfile,
  InvoiceDetail,
  InvoiceRecord,
  SubscriptionDetail,
  SubscriptionRecord,
  TaxMetadata,
} from "./types";
import "./portal.css";

function PortalState({
  loading,
  error,
  reload,
  children,
}: {
  loading: boolean;
  error: unknown;
  reload: () => void;
  children: ReactNode;
}) {
  if (loading) return <LoadingSkeleton label="Loading your records" />;
  if (error)
    return (
      <ErrorPanel
        title={
          error instanceof ApiError && error.status === 403
            ? "Access restricted"
            : error instanceof ApiError && error.status === 404
              ? "Record unavailable"
              : "Couldn’t load your records"
        }
        message={getErrorMessage(error)}
        onRetry={reload}
      />
    );
  return <>{children}</>;
}
function usePage() {
  const [search, setSearch] = useSearchParams();
  const value = Number(search.get("page") || "1");
  const page = Number.isSafeInteger(value) && value > 0 ? value : 1;
  return { page, change: (next: number) => setSearch({ page: String(next) }) };
}
function ServicePeriod({ start, end }: { start: string; end: string }) {
  return (
    <span className="portal-date-range">
      <DateLabel value={start} />
      <span>to before</span>
      <DateLabel value={end} />
    </span>
  );
}

function SnapshotAddress({ value }: { value: unknown }) {
  if (typeof value === "string") return <address>{value}</address>;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const address = value as Record<string, unknown>;
  const fields = ["line1", "line2", "city", "state", "postal_code", "country"];
  return (
    <address>
      {fields.map((field) =>
        typeof address[field] === "string" ? (
          <span key={field}>{address[field]}</span>
        ) : null,
      )}
    </address>
  );
}

export function SubscriptionListPage() {
  const { page, change } = usePage();
  const result = usePortalResource<ListResponse<SubscriptionRecord>>(
    `/portal/subscriptions?page=${page}&page_size=25`,
  );
  return (
    <section className="portal-page">
      <PageHeader
        title="My subscriptions"
        description="Your services and subscription dates, in one place."
      />
      <PortalState {...result}>
        {result.data && (
          <DataTable
            caption="My subscriptions"
            rows={result.data.items}
            columns={[
              {
                key: "number",
                header: "Subscription",
                render: (row) => (
                  <Link
                    className="portal-record-link"
                    to={`/portal/subscriptions/${encodeURIComponent(row.id)}`}
                  >
                    {row.number}
                    <ArrowUpRight size={13} aria-hidden="true" />
                  </Link>
                ),
              },
              {
                key: "state",
                header: "Status",
                render: (row) => <StatusBadge status={row.state} />,
              },
              {
                key: "dates",
                header: "Service period",
                render: (row) => (
                  <ServicePeriod start={row.start_date} end={row.end_date} />
                ),
              },
              {
                key: "close",
                header: "Scheduled closure",
                render: (row) =>
                  row.close_effective_on ? (
                    <DateLabel value={row.close_effective_on} />
                  ) : (
                    "—"
                  ),
              },
            ]}
            getRowKey={(row) => row.id}
            page={result.data.page}
            pageSize={result.data.page_size}
            total={result.data.total}
            onPageChange={change}
            emptyTitle="No subscriptions yet"
          />
        )}
      </PortalState>
    </section>
  );
}

export function InvoiceListPage() {
  const { page, change } = usePage();
  const result = usePortalResource<ListResponse<InvoiceRecord>>(
    `/portal/invoices?page=${page}&page_size=25`,
  );
  return (
    <section className="portal-page">
      <PageHeader
        title="My invoices"
        description="Your invoices, recorded payments and remaining balances."
      />
      <PortalState {...result}>
        {result.data && (
          <DataTable
            caption="My invoices"
            rows={result.data.items}
            columns={[
              {
                key: "number",
                header: "Invoice",
                render: (row) => (
                  <Link
                    className="portal-record-link"
                    to={`/portal/invoices/${encodeURIComponent(row.id)}`}
                  >
                    {row.number}
                    <ArrowUpRight size={13} aria-hidden="true" />
                  </Link>
                ),
              },
              {
                key: "due",
                header: "Due date",
                render: (row) => <DateLabel value={row.due_date} />,
              },
              {
                key: "total",
                header: "Total",
                render: (row) => (
                  <Money amount={row.total} currency={row.currency} />
                ),
              },
              {
                key: "paid",
                header: "Recorded payments",
                render: (row) => (
                  <Money amount={row.paid_amount} currency={row.currency} />
                ),
              },
              {
                key: "balance",
                header: "Balance",
                render: (row) => (
                  <div>
                    <Money amount={row.balance_due} currency={row.currency} />
                    {["DRAFT", "CANCELLED"].includes(row.status) && (
                      <p className="portal-muted">Not payable</p>
                    )}
                  </div>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (row) => (
                  <div className="portal-statuses">
                    <StatusBadge status={row.collection_status} />
                    {row.overdue && <StatusBadge status="OVERDUE" />}
                  </div>
                ),
              },
            ]}
            getRowKey={(row) => row.id}
            page={result.data.page}
            pageSize={result.data.page_size}
            total={result.data.total}
            onPageChange={change}
            emptyTitle="No invoices yet"
          />
        )}
      </PortalState>
    </section>
  );
}

export function SubscriptionDetailPage() {
  const { id = "" } = useParams();
  const result = usePortalResource<ResourceResponse<SubscriptionDetail>>(
    `/portal/subscriptions/${encodeURIComponent(id)}`,
  );
  const location = useLocation();
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const [notice, setNotice] = useState<{
    key: string;
    message: ReactNode;
  } | null>(null);
  const message =
    notice?.key === location.key
      ? notice.message
      : location.state?.renewalCreated
        ? "Your linked renewal draft was created. Brightloop staff will review and confirm it."
        : null;
  return (
    <section className="portal-page">
      <Link className="portal-back" to="/portal/subscriptions">
        <ArrowLeft size={15} aria-hidden="true" />
        My subscriptions
      </Link>
      <PageHeader
        title="My subscription"
        description={
          result.data?.data.number ||
          "Your service dates and available actions."
        }
      />
      <p
        ref={noticeRef}
        tabIndex={-1}
        className={message ? "portal-notice" : "portal-announcement"}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {message}
      </p>
      <PortalState {...result}>
        {result.data && (
          <SubscriptionContent
            key={id}
            subscription={result.data.data}
            prepareUpdate={result.prepareUpdate}
            announce={(message) => setNotice({ key: location.key, message })}
            returnFocusRef={noticeRef}
          />
        )}
      </PortalState>
    </section>
  );
}

function TaxRates({ taxes }: { taxes: TaxMetadata[] }) {
  return taxes.length ? (
    <span>
      {taxes.map((tax) => `${tax.name} (${tax.rate_percent}%)`).join(", ")}
    </span>
  ) : (
    <span>No applicable tax rules</span>
  );
}

function ActionNotice({
  row,
  action,
  cancelledPause,
}: {
  row: SubscriptionDetail;
  action: string;
  cancelledPause: boolean;
}) {
  if (action === "pause" && row.pause_interval)
    return (
      <>
        {row.paused ? "Service paused from" : "Pause scheduled for"}{" "}
        <DateLabel value={row.pause_interval.starts_on} />.
      </>
    );
  if (action === "resume" && row.resume_effective_on)
    return (
      <>
        Service resumes on <DateLabel value={row.resume_effective_on} />.
      </>
    );
  if (action === "resume" && cancelledPause && !row.pause_interval)
    return <>Your scheduled pause was cancelled.</>;
  if (action === "close" && row.close_effective_on)
    return (
      <>
        Closure takes effect on <DateLabel value={row.close_effective_on} />.
      </>
    );
  return <>Service schedule updated. Review the current dates below.</>;
}

function SubscriptionContent({
  subscription: row,
  prepareUpdate,
  announce,
  returnFocusRef,
}: {
  subscription: SubscriptionDetail;
  prepareUpdate: () => {
    isCurrent: () => boolean;
    apply: (response: ResourceResponse<SubscriptionDetail>) => boolean;
  };
  announce: (message: ReactNode) => void;
  returnFocusRef: RefObject<HTMLParagraphElement | null>;
}) {
  const navigate = useNavigate();
  const [reason, setReason] = useState("");
  const [renewStart, setRenewStart] = useState("");
  const [renewEnd, setRenewEnd] = useState("");
  const actions = (row.allowed_actions || [])
    .map((action) => action.toLowerCase())
    .filter((action) => ["pause", "resume", "close", "renew"].includes(action));
  const cancellingPause = Boolean(row.pause_effective_on);
  async function act(action: string) {
    const update = prepareUpdate();
    const payload =
      action === "renew"
        ? { start_date: renewStart, end_date: renewEnd }
        : reason.trim()
          ? { reason: reason.trim() }
          : {};
    const response = await apiClient.request<
      ResourceResponse<SubscriptionDetail>
    >(`/portal/subscriptions/${encodeURIComponent(row.id)}/${action}`, {
      method: "POST",
      json: payload,
    });
    if (!update.isCurrent()) return;
    if (action === "renew")
      navigate(
        `/portal/subscriptions/${encodeURIComponent(response.data.id)}`,
        { state: { renewalCreated: true } },
      );
    else if (update.apply(response)) {
      setReason("");
      announce(
        <ActionNotice
          row={response.data}
          action={action}
          cancelledPause={cancellingPause}
        />,
      );
    }
  }
  return (
    <div className="portal-detail-layout">
      <div className="portal-detail-main">
        <div className="portal-surface">
          <div className="portal-section-heading">
            <h2>{row.plan_snapshot.name || "Subscription"}</h2>
            <StatusBadge status={row.state} />
          </div>
          <SubscriptionStepper state={row.state} />
          <dl className="portal-facts">
            {row.prior_subscription_id && (
              <div>
                <dt>Renewed from</dt>
                <dd>
                  <Link
                    to={`/portal/subscriptions/${encodeURIComponent(row.prior_subscription_id)}`}
                  >
                    View previous subscription
                  </Link>
                </dd>
              </div>
            )}
            <div>
              <dt>Service starts</dt>
              <dd>
                <DateLabel value={row.start_date} />
              </dd>
            </div>
            <div>
              <dt>Service ends before</dt>
              <dd>
                <DateLabel value={row.end_date} />
              </dd>
            </div>
            <div>
              <dt>Payment terms</dt>
              <dd>{row.payment_terms_days} days</dd>
            </div>
            {row.plan_snapshot.cadence && (
              <div>
                <dt>Billing cadence</dt>
                <dd>{row.plan_snapshot.cadence.toLowerCase()}</dd>
              </div>
            )}
            {row.plan_snapshot.base_fee && (
              <div>
                <dt>Plan fee per cycle</dt>
                <dd>
                  <Money
                    amount={row.plan_snapshot.base_fee}
                    currency={row.currency}
                  />
                </dd>
              </div>
            )}
            <div>
              <dt>Recurring subtotal per cycle</dt>
              <dd>
                <Money
                  amount={row.recurring_subtotal}
                  currency={row.currency}
                />
                <p className="portal-muted">{row.recurring_subtotal_basis}</p>
              </dd>
            </div>
            <div>
              <dt>Plan fee tax rules</dt>
              <dd>
                <TaxRates taxes={row.base_fee_taxes} />
              </dd>
            </div>
            {row.expired && (
              <div>
                <dt>Service condition</dt>
                <dd>Service period ended</dd>
              </div>
            )}
            {row.pause_effective_on && (
              <div>
                <dt>Pause takes effect</dt>
                <dd>
                  <DateLabel value={row.pause_effective_on} />
                </dd>
              </div>
            )}
            {row.resume_effective_on && (
              <div>
                <dt>Service resumes</dt>
                <dd>
                  <DateLabel value={row.resume_effective_on} />
                </dd>
              </div>
            )}
            {row.next_billing_date && (
              <div>
                <dt>Next billing date</dt>
                <dd>
                  <DateLabel value={row.next_billing_date} />
                </dd>
              </div>
            )}
            {row.close_effective_on && (
              <div>
                <dt>Closure takes effect</dt>
                <dd>
                  <DateLabel value={row.close_effective_on} />
                </dd>
              </div>
            )}
            {row.paused && (
              <div>
                <dt>Service condition</dt>
                <dd>
                  <StatusBadge status="PAUSED" />
                </dd>
              </div>
            )}
          </dl>
        </div>
        <div className="portal-surface">
          <h2>Agreed product lines</h2>
          <p className="portal-muted">
            Tax preview for <DateLabel value={row.tax_preview_on} />.{" "}
            {row.tax_preview_basis}.
          </p>
          {row.lines.length ? (
            <div className="portal-table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit price</th>
                    <th>Line subtotal</th>
                    <th>Tax rules</th>
                  </tr>
                </thead>
                <tbody>
                  {row.lines.map((line) => (
                    <tr key={line.id}>
                      <td>{line.description}</td>
                      <td>{line.quantity}</td>
                      <td>
                        <Money
                          amount={line.unit_price}
                          currency={row.currency}
                        />
                      </td>
                      <td>
                        <Money
                          amount={line.line_total}
                          currency={row.currency}
                        />
                      </td>
                      <td>
                        <TaxRates taxes={line.taxes} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No product lines" />
          )}
        </div>
        {row.pause_interval && (
          <div className="portal-surface">
            <h2>{row.paused ? "Current pause" : "Scheduled pause"}</h2>
            <dl className="portal-facts">
              <div>
                <dt>Pause starts</dt>
                <dd>
                  <DateLabel value={row.pause_interval.starts_on} />
                </dd>
              </div>
              <div>
                <dt>Pause ends</dt>
                <dd>
                  {row.pause_interval.ends_on ? (
                    <DateLabel value={row.pause_interval.ends_on} />
                  ) : (
                    "No resume date scheduled"
                  )}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>
      <aside className="portal-detail-aside">
        <div className="portal-surface">
          <h2>Subscription invoices</h2>
          {row.invoice_references.length ? (
            <ul className="portal-document-list">
              {row.invoice_references.map((invoice) => (
                <li key={invoice.id}>
                  <Link
                    to={`/portal/invoices/${encodeURIComponent(invoice.id)}`}
                  >
                    <FileText size={16} aria-hidden="true" />
                    {invoice.number}
                    <StatusBadge status={invoice.status} />
                    <ArrowUpRight size={13} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="portal-muted">
              No invoices have been issued for this subscription.
            </p>
          )}
        </div>
        {actions.length > 0 && (
          <div className="portal-surface portal-actions">
            <h2>Manage your service</h2>
            <p className="portal-muted">
              Available actions follow your plan. The server confirms the
              effective date before your records update.
            </p>
            {actions.some((action) => action !== "renew") && (
              <FormField id="portal-action-reason" label="Reason (optional)">
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={2}
                />
              </FormField>
            )}
            <div className="portal-action-buttons">
              {actions
                .filter((action) => action !== "renew")
                .map((action) => (
                  <ConfirmDialog
                    key={action}
                    returnFocusRef={returnFocusRef}
                    title={
                      action === "resume" && cancellingPause
                        ? "Cancel scheduled pause?"
                        : `${action[0].toUpperCase()}${action.slice(1)} subscription?`
                    }
                    description={
                      action === "resume" && cancellingPause
                        ? "Cancel the scheduled pause request. Your updated service schedule will appear after the server confirms the change."
                        : "This changes your service schedule. Previously issued invoices remain unchanged. The resulting effective date will appear in your subscription."
                    }
                    confirmLabel={
                      action === "resume" && cancellingPause
                        ? "Cancel scheduled pause"
                        : `Confirm ${action}`
                    }
                    trigger={
                      <Button
                        variant={action === "close" ? "danger" : "secondary"}
                      >
                        {action === "resume" && cancellingPause
                          ? "Cancel scheduled pause"
                          : `${action[0].toUpperCase() + action.slice(1)} subscription`}
                      </Button>
                    }
                    onConfirm={() => act(action)}
                  />
                ))}
            </div>
            {actions.includes("renew") && (
              <div className="portal-renewal">
                <h3>Renew your subscription</h3>
                <p className="portal-muted">
                  Create a new draft for staff review. Renewal does not confirm
                  an invoice or record payment.
                </p>
                <FormField id="portal-renew-start" label="Renewal start date">
                  <input
                    type="date"
                    value={renewStart}
                    onChange={(event) => setRenewStart(event.target.value)}
                  />
                </FormField>
                <FormField
                  id="portal-renew-end"
                  label="Renewal ends before"
                  error={
                    renewStart && renewEnd && renewEnd <= renewStart
                      ? "End date must follow the start date."
                      : undefined
                  }
                >
                  <input
                    type="date"
                    value={renewEnd}
                    onChange={(event) => setRenewEnd(event.target.value)}
                  />
                </FormField>
                <ConfirmDialog
                  returnFocusRef={returnFocusRef}
                  title="Create a renewal draft?"
                  description="Brightloop staff will review and confirm the new subscription. Your current term and invoices remain unchanged."
                  confirmLabel="Create draft"
                  trigger={
                    <Button
                      disabled={
                        !renewStart || !renewEnd || renewEnd <= renewStart
                      }
                    >
                      Create renewal draft
                    </Button>
                  }
                  onConfirm={() => act("renew")}
                />
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

export function InvoiceDetailPage() {
  const { id = "" } = useParams();
  const result = usePortalResource<ResourceResponse<InvoiceDetail>>(
    `/portal/invoices/${encodeURIComponent(id)}`,
  );
  const row = result.data?.data;
  return (
    <section className="portal-page">
      <Link className="portal-back" to="/portal/invoices">
        <ArrowLeft size={15} aria-hidden="true" />
        My invoices
      </Link>
      <PageHeader
        title="My invoice"
        description={row?.number || "Your stored invoice and payment history."}
        actions={
          row && (
            <a
              className="ui-button ui-button--secondary"
              href={`/api/v1/portal/invoices/${encodeURIComponent(row.id)}/print`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Printer size={16} aria-hidden="true" />
              Print invoice
            </a>
          )
        }
      />
      <PortalState {...result}>
        {row && (
          <div className="portal-detail-layout">
            <div className="portal-detail-main">
              <div className="portal-surface">
                <div className="portal-section-heading">
                  <h2>{row.number}</h2>
                  <div className="portal-statuses">
                    <StatusBadge status={row.collection_status} />
                    {row.overdue && <StatusBadge status="OVERDUE" />}
                  </div>
                </div>
                <p className="portal-muted">
                  {row.seller_snapshot?.name || "Brightloop Software"}
                  {row.customer_snapshot?.display_name
                    ? ` · ${row.customer_snapshot.display_name}`
                    : ""}
                </p>
                <div className="portal-invoice-parties">
                  <div>
                    <h3>From</h3>
                    <p>{row.seller_snapshot?.name || "Brightloop Software"}</p>
                    <SnapshotAddress
                      value={
                        row.seller_snapshot?.billing_address ||
                        row.seller_snapshot?.address
                      }
                    />
                  </div>
                  <div>
                    <h3>Bill to</h3>
                    <p>{row.customer_snapshot?.display_name}</p>
                    {row.customer_snapshot?.company_name && (
                      <p>{row.customer_snapshot.company_name}</p>
                    )}
                    {row.customer_snapshot?.email && (
                      <p>{row.customer_snapshot.email}</p>
                    )}
                    <SnapshotAddress
                      value={row.customer_snapshot?.billing_address}
                    />
                  </div>
                </div>
                <dl className="portal-facts">
                  <div>
                    <dt>Invoice date</dt>
                    <dd>
                      <DateLabel value={row.invoice_date} />
                    </dd>
                  </div>
                  <div>
                    <dt>Due date</dt>
                    <dd>
                      <DateLabel value={row.due_date} />
                    </dd>
                  </div>
                  <div>
                    <dt>Service period</dt>
                    <dd>
                      <ServicePeriod
                        start={row.period_start}
                        end={row.period_end}
                      />
                    </dd>
                  </div>
                </dl>
                <div className="portal-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Description</th>
                        <th>Quantity</th>
                        <th>Unit price</th>
                        <th>Discount</th>
                        <th>Tax</th>
                        <th>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {row.lines.map((line) => (
                        <tr key={line.id}>
                          <td>
                            {line.description}
                            {line.taxes?.map((tax, index) => (
                              <p
                                className="portal-muted"
                                key={`${tax.name}-${index}`}
                              >
                                {tax.name} ({tax.rate_percent}%):{" "}
                                <Money
                                  amount={tax.amount}
                                  currency={row.currency}
                                />
                              </p>
                            ))}
                          </td>
                          <td>{line.quantity}</td>
                          <td>
                            <Money
                              amount={line.unit_price}
                              currency={row.currency}
                            />
                          </td>
                          <td>
                            <Money
                              amount={line.discount}
                              currency={row.currency}
                            />
                          </td>
                          <td>
                            <Money
                              amount={line.tax_total}
                              currency={row.currency}
                            />
                          </td>
                          <td>
                            <Money
                              amount={line.total}
                              currency={row.currency}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <dl className="portal-totals">
                  {[
                    ["Subtotal", row.subtotal],
                    ["Discount", row.discount_total],
                    ["Tax", row.tax_total],
                    ["Total", row.total],
                  ].map(([label, amount]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>
                        <Money amount={amount} currency={row.currency} />
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="portal-surface">
                <h2>Recorded payments</h2>
                {row.payments.length ? (
                  <div className="portal-table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Method</th>
                          <th>Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {row.payments.map((payment) => (
                          <tr key={payment.id}>
                            <td>
                              <DateLabel value={payment.paid_on} />
                            </td>
                            <td>{payment.method.replaceAll("_", " ")}</td>
                            <td>
                              <Money
                                amount={payment.amount}
                                currency={row.currency}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="portal-muted">
                    No payments have been recorded.
                  </p>
                )}
              </div>
            </div>
            <aside className="portal-detail-aside">
              <div className="portal-surface">
                <h2>Invoice balance</h2>
                <dl className="portal-totals">
                  <div>
                    <dt>Invoice total</dt>
                    <dd>
                      <Money amount={row.total} currency={row.currency} />
                    </dd>
                  </div>
                  <div>
                    <dt>Recorded payments</dt>
                    <dd>
                      <Money amount={row.paid_amount} currency={row.currency} />
                    </dd>
                  </div>
                  <div className="portal-balance">
                    <dt>
                      {["DRAFT", "CANCELLED"].includes(row.status)
                        ? "Document balance"
                        : "Remaining balance"}
                    </dt>
                    <dd>
                      <Money amount={row.balance_due} currency={row.currency} />
                    </dd>
                  </div>
                </dl>
                <p className="portal-muted">
                  {row.status === "CANCELLED"
                    ? "This invoice is cancelled. No payment is due. "
                    : row.status === "DRAFT"
                      ? "This is a draft invoice. Payment is not due yet. "
                      : ""}
                  Payments are recorded by Brightloop staff. Contact Brightloop
                  if a payment is missing.
                </p>
              </div>
            </aside>
          </div>
        )}
      </PortalState>
    </section>
  );
}

export function AccountPage() {
  const result =
    usePortalResource<ResourceResponse<CustomerProfile>>("/portal/me");
  const row = result.data?.data;
  return (
    <section className="portal-page">
      <PageHeader
        title="Account"
        description="Your Brightloop customer profile."
      />
      <PortalState {...result}>
        {row && (
          <div className="portal-surface portal-profile">
            <h2>{row.display_name}</h2>
            <dl className="portal-facts">
              <div>
                <dt>Email</dt>
                <dd>{row.email}</dd>
              </div>
              {row.company_name && (
                <div>
                  <dt>Company</dt>
                  <dd>{row.company_name}</dd>
                </div>
              )}
              <div>
                <dt>Billing address</dt>
                <dd>
                  {Object.values(row.billing_address).filter(Boolean).length ? (
                    <address>
                      {(
                        [
                          "line1",
                          "line2",
                          "city",
                          "state",
                          "postal_code",
                          "country",
                        ] as const
                      ).map((key) =>
                        row.billing_address[key] ? (
                          <span key={key}>{row.billing_address[key]}</span>
                        ) : null,
                      )}
                    </address>
                  ) : (
                    "No billing address recorded."
                  )}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </PortalState>
    </section>
  );
}
