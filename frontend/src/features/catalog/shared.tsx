import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  apiClient,
  getErrorMessage,
  isAbortError,
  type ListResponse,
} from "../../lib";
import { Button, ErrorPanel, FormField } from "../../components/ui";

export function useRecords<T>(path: string, query = "") {
  const [page, setPage] = useState(1);
  const [version, setVersion] = useState(0);
  const [data, setData] = useState<ListResponse<T> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setData(null);
    setError(null);
    apiClient
      .request<ListResponse<T>>(`${path}?page=${page}&page_size=25${query}`, {
        signal: controller.signal,
      })
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((error) => {
        if (!controller.signal.aborted && !isAbortError(error))
          setError(getErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, query, page, version]);
  return {
    data,
    error,
    loading,
    page,
    setPage,
    refresh: () => setVersion((value) => value + 1),
  };
}

export type Values = Record<string, string | boolean>;
export interface FieldSpec {
  key: string;
  label: string;
  type?:
    "text" | "email" | "date" | "checkbox" | "textarea" | "select" | "number";
  optional?: boolean;
  hint?: string;
  options?: string[];
  money?: boolean;
  signed?: boolean;
}
export function RecordEditor({
  title,
  fields,
  initial,
  onSave,
  onClose,
  children,
}: {
  title: string;
  fields: FieldSpec[];
  initial: Values;
  onSave: (values: Values) => Promise<void>;
  onClose: () => void;
  children?: ReactNode;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const values = Object.fromEntries(
      fields.map((field) => [
        field.key,
        field.type === "checkbox"
          ? form.has(field.key)
          : String(form.get(field.key) ?? "").trim(),
      ]),
    );
    setPending(true);
    setError(null);
    try {
      await onSave(values);
    } catch (error) {
      setError(getErrorMessage(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="catalog-editor" aria-label={title}>
      <header>
        <h2>{title}</h2>
        <Button variant="secondary" onClick={onClose} disabled={pending}>
          Close editor
        </Button>
      </header>
      <form onSubmit={(event) => void submit(event)}>
        <fieldset disabled={pending}>
          <div className="catalog-fields">
            {fields.map((field) => (
              <FormField
                key={field.key}
                id={`catalog-${field.key}`}
                label={field.label}
                hint={field.hint}
              >
                {field.type === "checkbox" ? (
                  <input
                    name={field.key}
                    type="checkbox"
                    defaultChecked={initial[field.key] === true}
                  />
                ) : field.type === "textarea" ? (
                  <textarea
                    name={field.key}
                    defaultValue={String(initial[field.key] ?? "")}
                    maxLength={10000}
                  />
                ) : field.type === "select" ? (
                  <select
                    name={field.key}
                    defaultValue={String(initial[field.key] ?? "")}
                    required={!field.optional}
                  >
                    {field.options?.map((option) => (
                      <option key={option}>{option}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    name={field.key}
                    type={field.money ? "text" : (field.type ?? "text")}
                    defaultValue={String(initial[field.key] ?? "")}
                    required={!field.optional}
                    maxLength={field.type === "email" ? 320 : 200}
                    inputMode={field.money ? "decimal" : undefined}
                    pattern={
                      field.money
                        ? field.signed
                          ? "-?\\d+(\\.\\d{1,2})?"
                          : "\\d+(\\.\\d{1,2})?"
                        : undefined
                    }
                    min={field.type === "number" ? 1 : undefined}
                    max={field.type === "number" ? 2147483647 : undefined}
                    step={field.type === "number" ? 1 : undefined}
                  />
                )}
              </FormField>
            ))}
          </div>
          {children}
        </fieldset>
        {error && <ErrorPanel message={error} />}
        <div className="catalog-form-actions">
          <Button type="submit" pending={pending}>
            Save changes
          </Button>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
        </div>
      </form>
    </section>
  );
}
export const text = (values: Values, key: string) => String(values[key] ?? "");
