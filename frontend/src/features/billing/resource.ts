import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient, ApiError, isAbortError } from '../../lib';

export function useResource<T>(path: string) {
  const [state, setState] = useState<{ data: T | null; error: unknown; loading: boolean }>({ data: null, error: null, loading: true });
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const abort = new AbortController();
    const serial = ++generation.current;
    setState({ data: null, error: null, loading: true });
    void apiClient.request<T>(path, { signal: abort.signal }).then(data => {
      if (!abort.signal.aborted && serial === generation.current) setState({ data, error: null, loading: false });
    }).catch(error => {
      if (!abort.signal.aborted && serial === generation.current && !isAbortError(error)) setState({ data: null, error, loading: false });
    });
    return () => abort.abort();
  }, [path, revision]);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  const replace = useCallback((data: T) => { generation.current += 1; setState({ data, error: null, loading: false }); }, []);
  return { ...state, reload, replace };
}

export function fieldError(error: unknown, name: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  const value = error.fields[name] ?? error.fields[`body.${name}`];
  return typeof value === 'string' ? value : undefined;
}
