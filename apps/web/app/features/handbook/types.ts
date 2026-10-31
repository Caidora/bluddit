export interface HandbookSection {
  slug: string;
  revision: number;
  title: string;
  body: string;
  updated_at: string;
  author_account_id: number;
  author_name: string;
}
export interface HandbookContent {
  title: string;
  body: string;
}
export interface HandbookCreate extends HandbookContent {
  slug: string;
}
export interface HandbookEdit extends HandbookContent {
  expected_revision: number;
}
