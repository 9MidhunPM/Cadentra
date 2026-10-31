import { useEffect, useState } from 'react';
import { apiClient, isAbortError } from '../../lib';

export function useResource<T>(path: string, revision = 0) {
  const [state, setState] = useState<{ data?: T; error?: unknown; loading: boolean }>({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    apiClient.request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ data, loading: false });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted && !isAbortError(error)) setState({ error, loading: false });
    });
    return () => controller.abort();
  }, [path, revision]);
  return state;
}
