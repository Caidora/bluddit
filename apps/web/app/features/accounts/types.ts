export type MembershipState = 'pending' | 'active' | 'rejected' | 'inactive';
export type Role = 'member' | 'officer' | 'guild_master';
export interface Account {
  id: number;
  username: string | null;
  battletag: string | null;
  display_name: string;
  membership_state: MembershipState;
  role_name: Role;
  timezone: string | null;
}
export interface AccountFilter {
  membership_state?: MembershipState;
  limit: number;
  offset: number;
}
export interface AccountPage {
  accounts: Account[];
  limit: number;
  offset: number;
}
export type AccountAction =
  | 'approve'
  | 'reject'
  | 'deactivate'
  | 'activate'
  | 'promote-to-officer'
  | 'demote-to-member'
  | 'pass-guild-master';
