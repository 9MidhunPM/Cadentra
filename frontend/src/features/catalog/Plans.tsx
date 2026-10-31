import { useState } from "react";
import { apiClient, useSession } from "../../lib";
import {
  Button,
  DataTable,
  DateLabel,
  ErrorPanel,
  LoadingSkeleton,
  Money,
  PageHeader,
  useToast,
} from "../../components/ui";
import { RecordEditor, text, useRecords, type FieldSpec } from "./shared";
import type { Plan } from "./types";
const fields: FieldSpec[] = [
  { key: "name", label: "Plan name" },
  {
    key: "base_fee",
    label: "Base fee per billing cycle (INR)",
    money: true,
    hint: "Product and variant lines are added separately. Use zero when products supply the full recurring charge.",
  },
  {
    key: "cadence",
    label: "Billing cadence",
    type: "select",
    options: ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"],
  },
  { key: "min_quantity", label: "Minimum product quantity", type: "number" },
  { key: "available_from", label: "Available from", type: "date" },
  {
    key: "available_until",
    label: "Available until (exclusive)",
    type: "date",
    optional: true,
    hint: "Leave blank for no end date.",
  },
  { key: "allow_pause", label: "Allow scheduled pause", type: "checkbox" },
  { key: "allow_early_close", label: "Allow early closure", type: "checkbox" },
  { key: "allow_renew", label: "Allow renewal", type: "checkbox" },
  {
    key: "auto_close",
    label: "Automatically close at expiry",
    type: "checkbox",
  },
];
function businessDate() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
interface TaxRule {
  id: string;
  name: string;
  rate_percent: string;
}
function TaxPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const rules = useRecords<TaxRule>("/tax-rules");
  const unseen = selected.filter(
    (id) => !rules.data?.items.some((rule) => rule.id === id),
  ).length;
  return (
    <fieldset className="catalog-tax-picker">
      <legend>Base-fee taxes</legend>
      <p className="catalog-note">
        Optional taxes applied to the plan's base fee. Configure tax rules in
        Billing.
      </p>
      {rules.loading && <LoadingSkeleton label="Loading tax rules" />}
      {rules.error && (
        <ErrorPanel
          title="Tax rules are unavailable"
          message="You can retry or save other plan changes. Existing tax assignments will be retained."
          onRetry={rules.refresh}
        />
      )}
      {!rules.loading && !rules.error && rules.data?.items.length === 0 && (
        <p className="catalog-note">No tax rules are configured yet.</p>
      )}
      {!rules.loading &&
        !rules.error &&
        rules.data?.items.map((rule) => (
          <label className="catalog-tax-option" key={rule.id}>
            <input
              type="checkbox"
              checked={selected.includes(rule.id)}
              onChange={(event) =>
                onChange(
                  event.target.checked
                    ? [...selected, rule.id]
                    : selected.filter((id) => id !== rule.id),
                )
              }
            />
            <span>
              {rule.name} · {rule.rate_percent}%
            </span>
          </label>
        ))}
      {unseen > 0 && (
        <p className="catalog-note">
          {unseen} saved tax{" "}
          {unseen === 1 ? "assignment is" : "assignments are"} retained outside
          this page.
        </p>
      )}
      {rules.data && rules.data.total > 25 && (
        <div className="catalog-actions">
          <Button
            variant="secondary"
            disabled={rules.loading || rules.page <= 1}
            onClick={() => rules.setPage(rules.page - 1)}
          >
            Previous taxes
          </Button>
          <span className="catalog-note">Tax rules page {rules.page}</span>
          <Button
            variant="secondary"
            disabled={rules.loading || rules.page * 25 >= rules.data.total}
            onClick={() => rules.setPage(rules.page + 1)}
          >
            More taxes
          </Button>
        </div>
      )}
    </fieldset>
  );
}
export function Plans() {
  const { actor } = useSession();
  const admin = actor?.role === "ADMIN";
  const list = useRecords<Plan>("/plans");
  const { toast } = useToast();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  const [selectedTaxes, setSelectedTaxes] = useState<string[]>([]);
  const item = editing && editing !== "new" ? editing : null;
  return (
    <>
      <PageHeader
        title="Plans"
        description="Set the billing cadence, base fee and service policies."
        actions={
          admin ? (
            <Button
              onClick={() => {
                setSelectedTaxes([]);
                setEditing("new");
              }}
            >
              New plan
            </Button>
          ) : undefined
        }
      />
      {!admin && (
        <p className="catalog-note">
          Catalog is read-only for staff. An administrator manages plan
          settings.
        </p>
      )}
      {editing && (
        <RecordEditor
          key={item?.id ?? "new"}
          title={item ? "Edit plan" : "New plan"}
          fields={fields}
          initial={{
            name: item?.name ?? "",
            base_fee: item?.base_fee ?? "0.00",
            cadence: item?.cadence ?? "MONTHLY",
            min_quantity: String(item?.min_quantity ?? 1),
            available_from: item?.available_from ?? businessDate(),
            available_until: item?.available_until ?? "",
            allow_pause: item?.allow_pause ?? false,
            allow_early_close: item?.allow_early_close ?? false,
            allow_renew: item?.allow_renew ?? false,
            auto_close: item?.auto_close ?? true,
          }}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await apiClient.request(item ? `/plans/${item.id}` : "/plans", {
              method: item ? "PATCH" : "POST",
              json: {
                name: text(values, "name"),
                base_fee: text(values, "base_fee"),
                currency: "INR",
                cadence: text(values, "cadence"),
                min_quantity: Number(text(values, "min_quantity")),
                available_from: text(values, "available_from"),
                available_until: text(values, "available_until") || null,
                allow_pause: values.allow_pause === true,
                allow_early_close: values.allow_early_close === true,
                allow_renew: values.allow_renew === true,
                auto_close: values.auto_close === true,
                tax_rule_ids: selectedTaxes,
              },
            });
            setEditing(null);
            list.refresh();
            toast("Plan saved.");
          }}
        >
          <TaxPicker selected={selectedTaxes} onChange={setSelectedTaxes} />
        </RecordEditor>
      )}
      {list.error && <ErrorPanel message={list.error} onRetry={list.refresh} />}{" "}
      {list.loading ? (
        <LoadingSkeleton label="Loading plans" />
      ) : (
        list.data && (
          <DataTable
            rows={list.data.items}
            getRowKey={(row) => row.id}
            page={list.page}
            pageSize={25}
            total={list.data.total}
            onPageChange={list.setPage}
            caption="Plans"
            emptyTitle="No plans yet"
            columns={[
              {
                key: "name",
                header: "Plan",
                render: (row) => (
                  <strong>
                    {row.name}
                    <small className="catalog-subtitle">
                      Minimum {row.min_quantity} product units
                    </small>
                  </strong>
                ),
              },
              {
                key: "fee",
                header: "Base fee / cycle",
                render: (row) => (
                  <Money amount={row.base_fee} currency={row.currency} />
                ),
              },
              {
                key: "cadence",
                header: "Cadence",
                render: (row) => row.cadence.toLowerCase(),
              },
              {
                key: "dates",
                header: "Availability",
                render: (row) => (
                  <span>
                    <DateLabel value={row.available_from} /> —{" "}
                    {row.available_until ? (
                      <DateLabel value={row.available_until} />
                    ) : (
                      "No end"
                    )}
                  </span>
                ),
              },
              {
                key: "policy",
                header: "Policies",
                render: (row) => (
                  <span>
                    {[
                      row.allow_pause && "Pause",
                      row.allow_early_close && "Early close",
                      row.allow_renew && "Renew",
                      row.auto_close && "Auto close",
                    ]
                      .filter(Boolean)
                      .join(" · ") || "Standard term"}
                  </span>
                ),
              },
              ...(admin
                ? [
                    {
                      key: "edit",
                      header: "Actions",
                      render: (row: Plan) => (
                        <Button
                          variant="secondary"
                          aria-label={`Edit ${row.name}`}
                          onClick={() => {
                            setSelectedTaxes([...row.tax_rule_ids]);
                            setEditing(row);
                          }}
                        >
                          Edit
                        </Button>
                      ),
                    },
                  ]
                : []),
            ]}
          />
        )
      )}
    </>
  );
}
