import { useEffect, useState } from "react";
import {
  apiClient,
  getErrorMessage,
  isAbortError,
  useSession,
  type ResourceResponse,
} from "../../lib";
import {
  Button,
  ConfirmDialog,
  DataTable,
  ErrorPanel,
  LoadingSkeleton,
  Money,
  PageHeader,
  StatusBadge,
  useToast,
} from "../../components/ui";
import { RecordEditor, text, useRecords, type FieldSpec } from "./shared";
import type { Product, ProductDetail, Variant } from "./types";
const productFields: FieldSpec[] = [
  { key: "name", label: "Product name" },
  { key: "product_type", label: "Product type" },
  { key: "sales_price", label: "Sales price (INR)", money: true },
  { key: "cost_price", label: "Internal cost (INR)", money: true },
  { key: "notes", label: "Notes", type: "textarea", optional: true },
  { key: "active", label: "Available for new subscriptions", type: "checkbox" },
];
const variantFields: FieldSpec[] = [
  { key: "attribute_name", label: "Attribute name" },
  { key: "attribute_value", label: "Attribute value" },
  {
    key: "price_delta",
    label: "Price adjustment (INR)",
    money: true,
    signed: true,
    hint: "Added to the product sales price. A negative adjustment is allowed if the resulting price is nonnegative.",
  },
  { key: "active", label: "Variant available", type: "checkbox" },
];
export function Products() {
  const { actor } = useSession();
  const admin = actor?.role === "ADMIN";
  const list = useRecords<Product>("/products");
  const { toast } = useToast();
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const [selected, setSelected] = useState<Product | null>(null);
  const item = editing && editing !== "new" ? editing : null;
  return (
    <>
      <PageHeader
        title="Products"
        description="Manage recurring products and their price-adjusting variants."
        actions={
          admin ? (
            <Button onClick={() => setEditing("new")}>New product</Button>
          ) : undefined
        }
      />
      {!admin && (
        <p className="catalog-note">
          Catalog is read-only for staff. An administrator manages prices.
        </p>
      )}
      {editing && (
        <RecordEditor
          key={item?.id ?? "new"}
          title={item ? "Edit product" : "New product"}
          fields={productFields}
          initial={{
            name: item?.name ?? "",
            product_type: item?.product_type ?? "SERVICE",
            sales_price: item?.sales_price ?? "0.00",
            cost_price: item?.cost_price ?? "0.00",
            notes: item?.notes ?? "",
            active: item?.active ?? true,
          }}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await apiClient.request(
              item ? `/products/${item.id}` : "/products",
              {
                method: item ? "PATCH" : "POST",
                json: {
                  name: text(values, "name"),
                  product_type: text(values, "product_type"),
                  sales_price: text(values, "sales_price"),
                  cost_price: text(values, "cost_price"),
                  notes: text(values, "notes") || null,
                  active: values.active === true,
                },
              },
            );
            setEditing(null);
            list.refresh();
            toast("Product saved.");
          }}
        />
      )}
      {list.error && <ErrorPanel message={list.error} onRetry={list.refresh} />}{" "}
      {list.loading ? (
        <LoadingSkeleton label="Loading products" />
      ) : (
        list.data && (
          <DataTable
            rows={list.data.items}
            getRowKey={(row) => row.id}
            page={list.page}
            pageSize={25}
            total={list.data.total}
            onPageChange={list.setPage}
            caption="Products"
            emptyTitle="No products yet"
            columns={[
              {
                key: "name",
                header: "Product",
                render: (row) => (
                  <strong>
                    {row.name}
                    <small className="catalog-subtitle">
                      {row.product_type}
                    </small>
                  </strong>
                ),
              },
              {
                key: "price",
                header: "Sales price",
                render: (row) => <Money amount={row.sales_price} />,
              },
              {
                key: "cost",
                header: "Internal cost",
                render: (row) => <Money amount={row.cost_price} />,
              },
              {
                key: "status",
                header: "Status",
                render: (row) => (
                  <StatusBadge status={row.active ? "ACTIVE" : "ARCHIVED"} />
                ),
              },
              {
                key: "actions",
                header: "Actions",
                render: (row) => (
                  <div className="catalog-actions">
                    <Button
                      variant="secondary"
                      onClick={() => setSelected(row)}
                    >
                      Variants for {row.name}
                    </Button>
                    {admin && (
                      <>
                        <Button
                          variant="secondary"
                          onClick={() => setEditing(row)}
                        >
                          Edit {row.name}
                        </Button>
                        <ConfirmDialog
                          title={
                            row.active ? "Archive product?" : "Restore product?"
                          }
                          description="Existing subscriptions and invoice snapshots retain their agreed prices."
                          confirmLabel={row.active ? "Archive" : "Restore"}
                          trigger={
                            <Button variant="secondary">
                              {row.active ? "Archive" : "Restore"}
                            </Button>
                          }
                          onConfirm={async () => {
                            await apiClient.request(`/products/${row.id}`, {
                              method: "PATCH",
                              json: { active: !row.active },
                            });
                            list.refresh();
                            toast(
                              row.active
                                ? "Product archived."
                                : "Product restored.",
                            );
                          }}
                        />
                      </>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )
      )}
      {selected && (
        <Variants
          key={selected.id}
          product={selected}
          admin={admin}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
function Variants({
  product,
  admin,
  onClose,
}: {
  product: Product;
  admin: boolean;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<Variant | "new" | null>(null);
  const { toast } = useToast();
  useEffect(() => {
    const abort = new AbortController();
    setError(null);
    apiClient
      .request<ResourceResponse<ProductDetail>>(`/products/${product.id}`, {
        signal: abort.signal,
      })
      .then((result) => {
        if (!abort.signal.aborted) setDetail(result.data);
      })
      .catch((error) => {
        if (!abort.signal.aborted && !isAbortError(error))
          setError(getErrorMessage(error));
      });
    return () => abort.abort();
  }, [product.id, version]);
  const item = editing && editing !== "new" ? editing : null;
  return (
    <section className="catalog-editor" aria-label={`${product.name} variants`}>
      <header>
        <div>
          <h2>{product.name} variants</h2>
          <p className="catalog-note">
            The server adds each adjustment to the agreed product price.
          </p>
        </div>
        <div className="catalog-actions">
          {admin && (
            <Button onClick={() => setEditing("new")}>Add variant</Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Close variants
          </Button>
        </div>
      </header>
      {error && (
        <ErrorPanel
          message={error}
          onRetry={() => setVersion((value) => value + 1)}
        />
      )}{" "}
      {editing && (
        <RecordEditor
          key={item?.id ?? "new"}
          title={item ? "Edit variant" : "New variant"}
          fields={variantFields}
          initial={{
            attribute_name: item?.attribute_name ?? "",
            attribute_value: item?.attribute_value ?? "",
            price_delta: item?.price_delta ?? "0.00",
            active: item?.active ?? true,
          }}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await apiClient.request(
              `/products/${product.id}/variants${item ? `/${item.id}` : ""}`,
              {
                method: item ? "PATCH" : "POST",
                json: {
                  attribute_name: text(values, "attribute_name"),
                  attribute_value: text(values, "attribute_value"),
                  price_delta: text(values, "price_delta"),
                  active: values.active === true,
                },
              },
            );
            setEditing(null);
            setVersion((value) => value + 1);
            toast("Variant saved.");
          }}
        />
      )}
      {!detail && !error && <LoadingSkeleton label="Loading variants" />}
      {detail && (
        <ul className="catalog-variant-list">
          {detail.variants.length ? (
            detail.variants.map((variant) => (
              <li key={variant.id}>
                <div>
                  <strong>
                    {variant.attribute_name}: {variant.attribute_value}
                  </strong>
                  <span>
                    Adjustment <Money amount={variant.price_delta} />
                  </span>
                  <StatusBadge
                    status={variant.active ? "ACTIVE" : "ARCHIVED"}
                  />
                </div>
                {admin && (
                  <Button
                    variant="secondary"
                    onClick={() => setEditing(variant)}
                  >
                    Edit variant {variant.attribute_value}
                  </Button>
                )}
              </li>
            ))
          ) : (
            <li>No variants yet.</li>
          )}
        </ul>
      )}
    </section>
  );
}
