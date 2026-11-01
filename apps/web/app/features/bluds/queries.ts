import { mutationOptions, queryOptions, type QueryClient } from '@tanstack/react-query';
import { bludsApi } from './api';
import type { BludContent, BludPatch } from './types';

export const bludKeys = {
  lists: (actor: number) => ['member', actor, 'bluds', 'list'] as const,
  detail: (actor: number, id: number) => ['member', actor, 'bluds', 'detail', id] as const,
};
export const referencesOptions = (actor: number) =>
  queryOptions({
    queryKey: ['member', actor, 'bluds', 'references'],
    queryFn: ({ signal }) => bludsApi.references(signal),
    staleTime: 60 * 60 * 1000,
    refetchInterval: (query) => (query.state.data?.refreshing ? 2000 : 60 * 60 * 1000),
  });
export const bludsOptions = (actor: number, search: string) =>
  queryOptions({
    queryKey: [...bludKeys.lists(actor), search],
    queryFn: ({ signal }) => bludsApi.list(search, signal),
  });
export const bludOptions = (actor: number, id: number) =>
  queryOptions({
    queryKey: bludKeys.detail(actor, id),
    queryFn: ({ signal }) => bludsApi.detail(id, signal),
  });
export const createOptions = (client: QueryClient, actor: number) =>
  mutationOptions({
    mutationFn: (body: BludContent) => bludsApi.create(body),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: bludKeys.lists(actor) });
    },
  });
export const updateOptions = (client: QueryClient, actor: number, id: number) =>
  mutationOptions({
    mutationFn: (body: BludPatch) => bludsApi.update(id, body),
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: bludKeys.lists(actor) }),
        client.invalidateQueries({ queryKey: bludKeys.detail(actor, id) }),
      ]);
    },
  });
