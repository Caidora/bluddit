import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAccount } from '@/components/session';
import { eventsApi } from './api';
import type { GuildEvent } from './types';

export const eventKeys = { all: (actor: number) => ['member', actor, 'events'] as const };
export const referencesOptions = (actor: number) =>
  queryOptions({
    queryKey: [...eventKeys.all(actor), 'references'],
    queryFn: ({ signal }) => eventsApi.references(signal),
    staleTime: 60 * 60 * 1000,
    refetchInterval: (query) => (query.state.data?.refreshing ? 2000 : 60 * 60 * 1000),
  });
export const listOptions = (actor: number, search: string) =>
  queryOptions({
    queryKey: [...eventKeys.all(actor), 'list', search],
    queryFn: ({ signal }) => eventsApi.list(search, signal),
  });
export const detailOptions = (actor: number, id: number) =>
  queryOptions({
    queryKey: [...eventKeys.all(actor), 'detail', id],
    queryFn: ({ signal }) => eventsApi.detail(id, signal),
    enabled: Number.isSafeInteger(id) && id > 0,
  });
export function useEventMutation<T>(mutationFn: (body: T) => Promise<GuildEvent>) {
  const actor = useAccount();
  const client = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: eventKeys.all(actor.id) });
    },
  });
}
