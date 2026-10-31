import { queryOptions } from '@tanstack/react-query';
import { permissionsApi } from './api';

export const policyKeys = { all: (actor: number) => ['member', actor, 'permissions'] as const };

export const policyOptions = (actor: number) =>
  queryOptions({
    queryKey: policyKeys.all(actor),
    queryFn: ({ signal }) => permissionsApi.permissions(signal),
  });
