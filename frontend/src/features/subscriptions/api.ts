import { apiClient } from '../../lib';
import type { ListResponse } from '../../lib';

/** Selectors enumerate real paginated records rather than silently truncating at 100. */
export async function allRecords<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const rows: T[] = [];
  for (let page = 1; ; page += 1) {
    const result = await apiClient.request<ListResponse<T>>(`${path}?page=${page}&page_size=100`, { signal });
    rows.push(...result.items);
    if (rows.length >= result.total || result.items.length === 0) return rows;
  }
}
