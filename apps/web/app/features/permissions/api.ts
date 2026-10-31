import { authenticated } from '@/features/auth/session';
import type { PermissionPolicy } from './types';

export const permissionsApi = {
  permissions(signal?: AbortSignal) {
    return authenticated<PermissionPolicy>('/api/permissions', { signal });
  },
};
