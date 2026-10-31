import { mutationOptions, queryOptions, type QueryClient } from '@tanstack/react-query';
import { handbookApi } from './api';
import type { HandbookCreate, HandbookEdit } from './types';

const keys = {
  all: (actor: number) => ['member', actor, 'handbook'] as const,
};
export const sectionsOptions = (actor: number, q = '') =>
  queryOptions({
    queryKey: [...keys.all(actor), 'list', q],
    queryFn: ({ signal }) => handbookApi.sections(q, signal),
  });
export const sectionOptions = (actor: number, slug: string) =>
  queryOptions({
    queryKey: [...keys.all(actor), 'section', slug],
    queryFn: ({ signal }) => handbookApi.section(slug, signal),
  });
export const revisionsOptions = (actor: number, slug: string, offset: number) =>
  queryOptions({
    queryKey: [...keys.all(actor), 'revisions', slug, offset],
    queryFn: ({ signal }) => handbookApi.revisions(slug, offset, signal),
  });
export const createOptions = (client: QueryClient, actor: number) =>
  mutationOptions({
    mutationFn: (section: HandbookCreate) => handbookApi.create(section),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: keys.all(actor) });
    },
  });
export const editOptions = (client: QueryClient, actor: number, slug: string) =>
  mutationOptions({
    mutationFn: (edit: HandbookEdit) => handbookApi.edit(slug, edit),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: keys.all(actor) });
    },
  });
