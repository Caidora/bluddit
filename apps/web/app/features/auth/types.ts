import type { Account } from '@/features/accounts/types';

export interface CurrentAccount extends Account {
  permissions: string[];
}
export interface Credentials {
  username: string;
  password: string;
}
export interface Registration extends Credentials {
  display_name: string;
}
export interface TokenResponse {
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
}
