import { useState } from "react";
import { apiClient, type ResourceResponse } from "../../lib";
import {
  Button,
  DataTable,
  ErrorPanel,
  LoadingSkeleton,
  PageHeader,
  useToast,
} from "../../components/ui";
import { RecordEditor, text, useRecords, type FieldSpec } from "./shared";
import type { Customer } from "./types";

const fields: FieldSpec[] = [
  { key: "display_name", label: "Customer name" },
  { key: "email", label: "Email", type: "email" },
  { key: "company_name", label: "Company", optional: true },
  { key: "line1", label: "Billing address", optional: true },
  { key: "city", label: "City", optional: true },
  { key: "postal_code", label: "Postal code", optional: true },
  { key: "country", label: "Country", optional: true },
];
export function Customers() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Customer | "new" | null>(null);
  const list = useRecords<Customer>(
    "/customers",
    query ? `&q=${encodeURIComponent(query)}` : "",
  );
  const { toast } = useToast();
  const item = editing && editing !== "new" ? editing : null;
  const initial = {
    display_name: item?.display_name ?? "",
    email: item?.email ?? "",
    company_name: item?.company_name ?? "",
    ...Object.fromEntries(
      ["line1", "city", "postal_code", "country"].map((key) => [
        key,
        String(item?.billing_address[key] ?? ""),
      ]),
    ),
  };
  return (
    <>
      <PageHeader
        title="Customers"
        description="Customer details and billing addresses, kept together."
        actions={
          <Button onClick={() => setEditing("new")}>New customer</Button>
        }
      />
      <form
        className="catalog-search"
        onSubmit={(event) => {
          event.preventDefault();
          list.setPage(1);
          setQuery(search.trim());
        }}
      >
        <label htmlFor="customer-search">Search customers</label>
        <input
          id="customer-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          maxLength={200}
          placeholder="Name or email"
        />
        <Button variant="secondary" type="submit">
          Search
        </Button>
      </form>
      {editing && (
        <RecordEditor
          key={item?.id ?? "new"}
          title={item ? "Edit customer" : "New customer"}
          fields={fields}
          initial={initial}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await apiClient.request<ResourceResponse<Customer>>(
              item ? `/customers/${item.id}` : "/customers",
              {
                method: item ? "PATCH" : "POST",
                json: {
                  display_name: text(values, "display_name"),
                  email: text(values, "email"),
                  company_name: text(values, "company_name") || null,
                  billing_address: {
                    ...(item?.billing_address ?? {}),
                    ...Object.fromEntries(
                      ["line1", "city", "postal_code", "country"].map((key) => [
                        key,
                        text(values, key),
                      ]),
                    ),
                  },
                },
              },
            );
            setEditing(null);
            list.refresh();
            toast("Customer saved.");
          }}
        />
      )}
      {list.error && <ErrorPanel message={list.error} onRetry={list.refresh} />}
      {list.loading ? (
        <LoadingSkeleton label="Loading customers" />
      ) : (
        list.data && (
          <DataTable
            rows={list.data.items}
            getRowKey={(row) => row.id}
            page={list.page}
            pageSize={25}
            total={list.data.total}
            onPageChange={list.setPage}
            caption="Customers"
            emptyTitle="No customers yet"
            columns={[
              {
                key: "name",
                header: "Customer",
                render: (row) => <strong>{row.display_name}</strong>,
              },
              { key: "email", header: "Email", render: (row) => row.email },
              {
                key: "company",
                header: "Company",
                render: (row) => row.company_name || "—",
              },
              {
                key: "edit",
                header: "Actions",
                render: (row) => (
                  <Button variant="secondary" onClick={() => setEditing(row)}>
                    Edit {row.display_name}
                  </Button>
                ),
              },
            ]}
          />
        )
      )}
    </>
  );
}
