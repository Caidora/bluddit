export type DungeonStatus = 'not_completed' | 'completed' | 'completed_rerun';
export interface Choice {
  id: string;
  name: string;
}
export interface References {
  version: string;
  reviewed_on: string;
  sources: { label: string; url: string }[];
  classes: (Choice & { specs: Choice[] })[];
  professions: (Choice & { category: 'primary' | 'secondary'; max_level: number })[];
  zones: Choice[];
  dungeons: (Choice & {
    location: string;
    suggested_level_min: number;
    suggested_level_max: number;
    guide_url: string | null;
    quest_guide_url: string | null;
    source_urls: string[];
  })[];
  dungeon_statuses: Choice[];
  max_primary_professions: number;
}
export interface BludContent {
  name: string;
  class_id: string;
  spec_id: string | null;
  character_created_on: string;
  farming_zone_id: string | null;
}
export interface ProfessionInput {
  profession_id: string;
  level: number | null;
}
export interface DungeonInput {
  dungeon_id: string;
  status: DungeonStatus;
}
export interface Blud extends BludContent {
  blud_id: number;
  account_id: number;
  owner_name: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
  updated_by_account_id: number;
  farming_zone_updated_at: string | null;
  professions: (ProfessionInput & { updated_at: string })[];
  dungeons: (DungeonInput & { updated_at: string })[];
  completed_dungeons: number;
  rerun_dungeons: number;
  total_dungeons: number;
}
export type BludPatch = Partial<BludContent> & {
  archived?: boolean;
  professions?: ProfessionInput[];
  dungeons?: DungeonInput[];
};
export interface BludList {
  bluds: Blud[];
  limit: number;
  offset: number;
  has_more: boolean;
}
