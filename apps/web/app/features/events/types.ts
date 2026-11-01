export interface Choice {
  id: string;
  name: string;
}
export interface References {
  refreshing: boolean;
  activities: Choice[];
  dungeons: (Choice & { active: boolean })[];
  timezones: string[];
}
export interface Schedule {
  local_start: string;
  scheduling_timezone: string;
  occurrence?: 'earlier' | 'later';
}
export interface Candidate {
  starts_at: string;
  utc_offset: string;
  occurrence: 'earlier' | 'later';
}
export interface Preview {
  status: 'valid' | 'ambiguous' | 'nonexistent';
  candidates: Candidate[];
}
export interface EventContent extends Schedule {
  title: string;
  activity_type: string;
  dungeon_id: string | null;
  duration_minutes: number | null;
  capacity: number | null;
  requirements: string;
}
export interface GuildEvent {
  event_id: number;
  title: string;
  activity_type: string;
  dungeon_id: string | null;
  starts_at: string;
  scheduling_timezone: string;
  duration_minutes: number | null;
  capacity: number | null;
  requirements: string;
  state: 'scheduled' | 'cancelled';
  created_by_account_id: number;
  updated_by_account_id: number;
  created_at: string;
  updated_at: string;
  organizers: { account_id: number; display_name: string; active: boolean }[];
}
export interface EventList {
  events: GuildEvent[];
  limit: number;
  offset: number;
  has_more: boolean;
}
