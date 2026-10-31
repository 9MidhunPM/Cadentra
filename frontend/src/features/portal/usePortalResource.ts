import { useEffect, useState } from 'react'
import { apiClient, isAbortError } from '../../lib'

export function usePortalResource<T>(path: string) {
  const [revision, setRevision] = useState(0)
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: unknown }>({ data: null, loading: true, error: null })
  useEffect(() => {
    const controller = new AbortController()
    setState({ data: null, loading: true, error: null })
    void apiClient.request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ data, loading: false, error: null })
    }).catch(error => {
      if (!controller.signal.aborted && !isAbortError(error)) setState({ data: null, loading: false, error })
    })
    return () => controller.abort()
  }, [path, revision])
  return { ...state, reload: () => setRevision(value => value + 1) }
}
