import { authenticated } from '@/features/auth/session';
import type { Blud, BludContent, BludList, BludPatch, References } from './types';

export const bludsApi = {
  references: (signal?: AbortSignal) =>
    authenticated<References>('/api/bluds/reference-data', { signal }),
  list: (search: string, signal?: AbortSignal) =>
    authenticated<BludList>(`/api/bluds?${search}`, { signal }),
  detail: (id: number, signal?: AbortSignal) => authenticated<Blud>(`/api/bluds/${id}`, { signal }),
  create: (body: BludContent) =>
    authenticated<Blud>('/api/bluds', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: BludPatch) =>
    authenticated<Blud>(`/api/bluds/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
};
