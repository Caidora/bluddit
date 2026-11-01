import { authenticated } from '@/features/auth/session';
import type { HandbookCreate, HandbookEdit, HandbookSection } from './types';

export const handbookApi = {
  sections(q: string, signal?: AbortSignal) {
    return authenticated<{ sections: HandbookSection[] }>(
      `/api/handbook?${new URLSearchParams({ q })}`,
      {
        signal,
      }
    ).then((response) => response.sections);
  },
  section(slug: string, signal?: AbortSignal) {
    return authenticated<HandbookSection>(`/api/handbook/${encodeURIComponent(slug)}`, { signal });
  },
  revisions(slug: string, offset: number, signal?: AbortSignal) {
    return authenticated<{ revisions: HandbookSection[]; limit: number; offset: number }>(
      `/api/handbook/${encodeURIComponent(slug)}/revisions?limit=10&offset=${offset}`,
      { signal }
    ).then((response) => response.revisions);
  },
  create(section: HandbookCreate) {
    return authenticated<HandbookSection>('/api/handbook', {
      method: 'POST',
      body: JSON.stringify(section),
    });
  },
  edit(slug: string, edit: HandbookEdit) {
    return authenticated<HandbookSection>(`/api/handbook/${encodeURIComponent(slug)}`, {
      method: 'PUT',
      body: JSON.stringify(edit),
    });
  },
  delete(slug: string, expectedRevision: number) {
    return authenticated<void>(
      `/api/handbook/${encodeURIComponent(slug)}?expected_revision=${expectedRevision}`,
      { method: 'DELETE' }
    );
  },
};
