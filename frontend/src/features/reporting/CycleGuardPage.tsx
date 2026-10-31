import { useEffect, useState, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router";
import {
  ArrowUpRight,
  Clock3,
  MailWarning,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import {
  apiClient,
  getErrorMessage,
  isAbortError,
  type ListResponse,
} from "../../lib";
import {
  Button,
  DataTable,
  DateLabel,
  ErrorPanel,
  LoadingSkeleton,
  Money,
  PageHeader,
} from "../../components/ui";
import { CustomerFilter } from "./CustomerFilter";
import "./cycleguard.css";
import "./reporting.css";

export type CycleGuardKind = "OVERDUE" | "BILLING_DUE" | "EMAIL_FAILED";
interface CycleGuardItem {
  id: string;
  kind: CycleGuardKind;
  record_id: string;
  record_type: "invoice" | "subscription";
  label: string;
  reason: string;
  occurred_on: string;
  amount: string | null;
  currency: string | null;
  attempts: number | null;
  next_attempt_at: string | null;
  error_code: string | null;
}
interface Queue extends ListResponse<CycleGuardItem> {
  as_of: string;
}
const categories = [
  {
    kind: "OVERDUE",
    label: "Overdue invoices",
    icon: TriangleAlert,
    description:
      "Confirmed invoices with a remaining balance after their due date.",
  },
  {
    kind: "BILLING_DUE",
    label: "Billing due",
    icon: Clock3,
    description:
      "Subscription billing periods awaiting a recorded outcome, including paused periods awaiting processing.",
  },
  {
    kind: "EMAIL_FAILED",
    label: "Invoice email failures",
    icon: MailWarning,
    description:
      "Invoice notifications whose delivery attempt needs attention. Password-reset emails are excluded.",
  },
] as const;

function deliveryMessage(code: string | null) {
  if (!code) return "Delivery attempt failed";
  if (code === "SMTP_AUTH")
    return "Mail provider authentication failed";
  if (code === "SMTP_RECIPIENT") return "Recipient was rejected";
  if (code === "SMTP_SENDER") return "Sender was rejected";
  if (code === "SMTP_CONNECTION") return "Mail provider connection failed";
  if (code === "INVALID_CONTENT") return "Invoice email content needs review";
  return "Mail delivery could not be completed";
}
function RetryDate({ value }: { value: string }) {
  const timestamp = new Date(value);
  if (!Number.isFinite(timestamp.getTime())) return null;
  return (
    <span className="cycle-guard-secondary">
      Next retry eligible:{" "}
      <time dateTime={value}>
        {new Intl.DateTimeFormat("en-IN", {
          timeZone: "Asia/Kolkata",
          day: "numeric",
          month: "short",
          hour: "numeric",
          minute: "2-digit",
          timeZoneName: "short",
        }).format(timestamp)}
      </time>
    </span>
  );
}

export function CycleGuardPage() {
  const [params, setParams] = useSearchParams();
  const selected =
    categories.find((item) => item.kind === params.get("kind")) ??
    categories[0];
  const customerId = params.get("customer_id") ?? "";
  const candidate = Number(params.get("page") ?? "1");
  const page =
    Number.isSafeInteger(candidate) && candidate >= 1 ? candidate : 1;
  const [customer, setCustomer] = useState({ id: "", name: "" });
  const [revision, setRevision] = useState(0);
  const query = new URLSearchParams({
    kind: selected.kind,
    page: String(page),
    page_size: "25",
  });
  if (customerId) query.set("customer_id", customerId);
  const path = `/reports/cycleguard?${query}`;
  const [resource, setResource] = useState<{
    path: string;
    data: Queue | null;
    loading: boolean;
    error: string | null;
  }>({ path, data: null, loading: true, error: null });
  useEffect(() => {
    const controller = new AbortController();
    setResource({ path, data: null, loading: true, error: null });
    apiClient
      .request<Queue>(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted)
          setResource({ path, data, loading: false, error: null });
      })
      .catch((error) => {
        if (!controller.signal.aborted && !isAbortError(error))
          setResource({
            path,
            data: null,
            loading: false,
            error: getErrorMessage(error),
          });
      });
    return () => controller.abort();
  }, [path, revision]);
  const current =
    resource.path === path
      ? resource
      : { data: null, loading: true, error: null };
  function change(values: {
    kind?: CycleGuardKind;
    customer_id?: string;
    page?: number;
  }) {
    setParams((previous) => {
      const next = new URLSearchParams();
      next.set("kind", values.kind ?? selected.kind);
      next.set("page", String(values.page ?? 1));
      const owner = values.customer_id ?? previous.get("customer_id") ?? "";
      if (owner) next.set("customer_id", owner);
      return next;
    });
  }
  function tabKeys(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | null = null;
    if (event.key === "ArrowRight") next = (index + 1) % categories.length;
    if (event.key === "ArrowLeft")
      next = (index + categories.length - 1) % categories.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = categories.length - 1;
    if (next === null) return;
    event.preventDefault();
    change({ kind: categories[next].kind });
    document.getElementById(`cycle-tab-${categories[next].kind}`)?.focus();
  }
  const total = current.data?.total;
  return (
    <section className="cycle-guard">
      <PageHeader
        eyebrow="BILLING HEALTH"
        title="CycleGuard"
        description="Every exception has a reason. Every reason leads to a record."
        actions={
          <Button
            variant="secondary"
            onClick={() => setRevision((value) => value + 1)}
          >
            <RefreshCw size={15} aria-hidden="true" />
            Refresh queue
          </Button>
        }
      />
      <div className="cycle-guard-intro">
        <span className="cycle-guard-mark">
          <ShieldCheck size={24} aria-hidden="true" />
        </span>
        <div>
          <h2>A clear next place to look.</h2>
          <p>
            Review overdue balances, pending billing cycles and invoice email
            failures from your stored records. Opening this view does not run
            billing or resend email.
          </p>
        </div>
        <span className="cycle-guard-readonly">Read-only review</span>
      </div>
      <div className="cycle-guard-toolbar">
        <div
          className="cycle-guard-tabs"
          role="tablist"
          aria-label="Billing health categories"
        >
          {categories.map((category, index) => {
            const Icon = category.icon;
            return (
              <button
                key={category.kind}
                id={`cycle-tab-${category.kind}`}
                role="tab"
                type="button"
                aria-selected={selected.kind === category.kind}
                aria-controls="cycle-guard-panel"
                tabIndex={selected.kind === category.kind ? 0 : -1}
                onClick={() => change({ kind: category.kind })}
                onKeyDown={(event) => tabKeys(event, index)}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{category.label}</span>
              </button>
            );
          })}
        </div>
        <CustomerFilter
          selectedId={customerId}
          selectedName={
            customer.id === customerId ? customer.name : "Selected customer"
          }
          onChange={(id, name) => {
            setCustomer({ id, name });
            change({ customer_id: id });
          }}
        />
      </div>
      <section
        id="cycle-guard-panel"
        role="tabpanel"
        aria-labelledby={`cycle-tab-${selected.kind}`}
        className="cycle-guard-panel"
      >
        <header className="cycle-guard-panel-header">
          <div>
            <h2>{selected.label}</h2>
            <p>{selected.description}</p>
          </div>
          {current.data && (
            <div className="cycle-guard-count">
              <strong>{total}</strong>
              <span>
                matching {total === 1 ? "record" : "records"} · as of{" "}
                <DateLabel value={current.data.as_of} />
              </span>
            </div>
          )}
        </header>
        {current.loading && (
          <LoadingSkeleton label={`Loading ${selected.label.toLowerCase()}`} />
        )}
        {current.error && (
          <ErrorPanel
            title="Queue unavailable"
            message={current.error}
            onRetry={() => setRevision((value) => value + 1)}
          />
        )}
        {current.data && (
          <DataTable
            caption={selected.label}
            rows={current.data.items}
            getRowKey={(row) => row.id}
            page={current.data.page}
            pageSize={current.data.page_size}
            total={current.data.total}
            onPageChange={(page) => change({ page })}
            emptyTitle={`No ${selected.label.toLowerCase()} found`}
            columns={[
              {
                key: "record",
                header: "Record",
                render: (row) => (
                  <Link
                    className="cycle-guard-link"
                    to={
                      row.record_type === "invoice"
                        ? `/billing/invoices/${encodeURIComponent(row.record_id)}`
                        : `/subscriptions/${encodeURIComponent(row.record_id)}`
                    }
                  >
                    {row.label}
                    <ArrowUpRight size={14} aria-hidden="true" />
                  </Link>
                ),
              },
              {
                key: "reason",
                header: "Why it appears",
                render: (row) => (
                  <div className="cycle-guard-reason">
                    {row.reason}
                    {row.kind === "EMAIL_FAILED" && (
                      <>
                        <span className="cycle-guard-secondary">
                          {deliveryMessage(row.error_code)}
                          {row.attempts !== null
                            ? ` · ${row.attempts} ${row.attempts === 1 ? "attempt" : "attempts"}`
                            : ""}
                        </span>
                        {row.next_attempt_at && (
                          <RetryDate value={row.next_attempt_at} />
                        )}
                      </>
                    )}
                  </div>
                ),
              },
              {
                key: "date",
                header:
                  selected.kind === "OVERDUE"
                    ? "Due date"
                    : selected.kind === "BILLING_DUE"
                      ? "Cycle starts"
                      : "Queued on",
                render: (row) => <DateLabel value={row.occurred_on} />,
              },
              {
                key: "amount",
                header:
                  selected.kind === "OVERDUE"
                    ? "Balance due"
                    : "Recorded amount",
                render: (row) =>
                  row.amount !== null && row.currency ? (
                    <Money amount={row.amount} currency={row.currency} />
                  ) : (
                    <span className="cycle-guard-secondary">
                      Not applicable
                    </span>
                  ),
              },
            ]}
          />
        )}
      </section>
      <p className="cycle-guard-footnote">
        CycleGuard explains recorded conditions. It does not forecast revenue,
        verify bank transfers or confirm external email delivery.
      </p>
    </section>
  );
}
