import { useEffect, useRef, useState } from "react";
import { apiClient, isAbortError } from "../../lib";

export function usePortalResource<T>(path: string) {
  const [revision, setRevision] = useState(0);
  const active = useRef<{
    path: string;
    cancelled: boolean;
    replaced: boolean;
    controller: AbortController;
  } | null>(null);
  const [state, setState] = useState<{
    path: string;
    data: T | null;
    loading: boolean;
    error: unknown;
  }>({ path, data: null, loading: true, error: null });
  useEffect(() => {
    const request = {
      path,
      cancelled: false,
      replaced: false,
      controller: new AbortController(),
    };
    active.current = request;
    setState({ path, data: null, loading: true, error: null });
    void apiClient
      .request<T>(path, { signal: request.controller.signal })
      .then((data) => {
        if (!request.cancelled && !request.replaced)
          setState({ path, data, loading: false, error: null });
      })
      .catch((error) => {
        if (!request.cancelled && !request.replaced && !isAbortError(error))
          setState({ path, data: null, loading: false, error });
      });
    return () => {
      request.cancelled = true;
      request.controller.abort();
    };
  }, [path, revision]);

  // Capture the current read, so a completed mutation cannot replace a later
  // route or retry. A complete action DTO also supersedes any earlier GET.
  function prepareUpdate() {
    const request = active.current;
    const isCurrent = () =>
      Boolean(request && !request.cancelled && active.current === request);
    const apply = (data: T) => {
      if (!request || !isCurrent()) return false;
      request.replaced = true;
      request.controller.abort();
      setState({ path: request.path, data, loading: false, error: null });
      return true;
    };
    return { isCurrent, apply };
  }

  return {
    ...(state.path === path
      ? state
      : { data: null, loading: true, error: null }),
    reload: () => setRevision((value) => value + 1),
    prepareUpdate,
  };
}
