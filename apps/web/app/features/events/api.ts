import { authenticated } from '@/features/auth/session';
import type {
  EventContent,
  EventList,
  GuildEvent,
  Preview,
  References,
  Schedule,
} from './types';

export const eventsApi = {
  references: (signal?: AbortSignal) =>
    authenticated<References>('/api/events/reference-data', { signal }),
  list: (search: string, signal?: AbortSignal) =>
    authenticated<EventList>(`/api/events?${search}`, { signal }),
  detail: (id: number, signal?: AbortSignal) =>
    authenticated<GuildEvent>(`/api/events/${id}`, { signal }),
  preview: (body: Schedule, signal?: AbortSignal) =>
    authenticated<Preview>('/api/events/preview-start', {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    }),
  create: (body: EventContent) =>
    authenticated<GuildEvent>('/api/events', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: number, body: Partial<EventContent>) =>
    authenticated<GuildEvent>(`/api/events/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  cancel: (id: number) =>
    authenticated<GuildEvent>(`/api/events/${id}/cancel`, { method: 'POST' }),
  organizers: (id: number, account_ids: number[]) =>
    authenticated<GuildEvent>(`/api/events/${id}/organizers`, {
      method: 'PUT',
      body: JSON.stringify({ account_ids }),
    }),
};
