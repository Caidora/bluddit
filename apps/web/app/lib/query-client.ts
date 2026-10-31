import { QueryClient } from '@tanstack/react-query';
import { ApiError } from './http';

export const memberKeys = { all: ['member'] as const };

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 0,
        retry: (count, error) =>
          count < 1 && error instanceof ApiError && (error.status === 0 || error.status >= 500),
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false, gcTime: 0 },
    },
  });
}
