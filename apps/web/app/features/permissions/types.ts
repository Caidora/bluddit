import type { Role } from '@/features/accounts/types';

export interface PermissionPolicy {
  permissions: string[];
  roles: Record<Role, string[]>;
}
