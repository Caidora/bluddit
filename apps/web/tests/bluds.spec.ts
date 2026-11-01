import { test, expect, type BrowserContext } from '@playwright/test';
import { mockApi, member, officer, noOverflow } from './fixtures';
import type { Blud, References } from '../app/features/bluds/types';

const references: References = {
  version: 'synthetic-1',
  reviewed_on: '2026-11-01',
  sources: [],
  max_primary_professions: 2,
  classes: [
    { id: 'mage', name: 'Mage', specs: [{ id: 'mage-frost', name: 'Frost' }] },
    { id: 'warrior', name: 'Warrior', specs: [{ id: 'warrior-arms', name: 'Arms' }] },
  ],
  professions: [
    { id: 'mining', name: 'Mining', category: 'primary', max_level: 300 },
    { id: 'alchemy', name: 'Alchemy', category: 'primary', max_level: 300 },
    { id: 'tailoring', name: 'Tailoring', category: 'primary', max_level: 300 },
    { id: 'cooking', name: 'Cooking', category: 'secondary', max_level: 300 },
  ],
  zones: [
    { id: 'westfall', name: 'Westfall' },
    { id: 'riverglades', name: 'Riverglades' },
  ],
  dungeons: [
    {
      id: 'ragefire-chasm',
      name: 'Ragefire Chasm',
      location: 'Orgrimmar',
      suggested_level_min: 13,
      suggested_level_max: 18,
      guide_url: 'https://www.icy-veins.com/wow-forever/ragefire-chasm-guide',
      quest_guide_url: null,
      source_urls: [],
    },
    {
      id: 'hall-of-thanes',
      name: 'Hall of Thanes',
      location: 'Dun Morogh',
      suggested_level_min: 13,
      suggested_level_max: 18,
      guide_url: null,
      quest_guide_url: null,
      source_urls: [],
    },
  ],
  dungeon_statuses: [
    { id: 'not_completed', name: 'Not completed' },
    { id: 'completed', name: 'Completed' },
    { id: 'completed_rerun', name: 'Completed — looking to rerun' },
  ],
};
const original: Blud = {
  blud_id: 10,
  account_id: 1,
  owner_name: 'River',
  name: 'Riverfrost',
  class_id: 'mage',
  spec_id: null,
  character_created_on: '2026-10-28',
  farming_zone_id: null,
  farming_zone_updated_at: null,
  archived: false,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
  updated_by_account_id: 1,
  professions: [],
  dungeons: [],
  completed_dungeons: 0,
  rerun_dungeons: 0,
  total_dungeons: 2,
};
async function bludsApi(context: BrowserContext, initial = [original]) {
  const state = {
    bluds: structuredClone(initial),
    error: 0,
    failReads: false,
    writes: 0,
    searches: [] as string[],
  };
  await context.route('**/api/bluds**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith('/reference-data')) return route.fulfill({ json: references });
    const method = request.method();
    const id = Number(url.pathname.split('/')[3]);
    if (method !== 'GET') {
      state.writes++;
      expect(request.headers()['x-csrf-protection']).toBe('1');
      const body = request.postDataJSON();
      expect(body).not.toHaveProperty('expected_revision');
      expect(body).not.toHaveProperty('account_id');
      if (state.error)
        return route.fulfill({ status: state.error, json: { detail: 'Database unavailable' } });
      if (method === 'POST') {
        const created = { ...original, ...body, blud_id: 20 };
        state.bluds.push(created);
        return route.fulfill({ status: 201, json: created });
      }
      const old = state.bluds.find((item) => item.blud_id === id)!;
      const updated: Blud = { ...old, ...body };
      if (body.professions)
        updated.professions = body.professions.map((item: object) => ({
          ...item,
          updated_at: '2026-11-01T01:00:00Z',
        }));
      if (body.dungeons) {
        updated.dungeons = [
          ...old.dungeons.filter(
            (item) =>
              !body.dungeons.some(
                (patch: { dungeon_id: string }) => patch.dungeon_id === item.dungeon_id
              )
          ),
          ...body.dungeons.map((item: object) => ({ ...item, updated_at: '2026-11-01T01:00:00Z' })),
        ];
        updated.completed_dungeons = updated.dungeons.filter(
          (item) => item.status !== 'not_completed'
        ).length;
        updated.rerun_dungeons = updated.dungeons.filter(
          (item) => item.status === 'completed_rerun'
        ).length;
      }
      if ('farming_zone_id' in body) updated.farming_zone_updated_at = '2026-11-01T01:00:00Z';
      state.bluds = state.bluds.map((item) => (item.blud_id === id ? updated : item));
      return route.fulfill({ json: updated });
    }
    if (state.failReads)
      return route.fulfill({ status: 503, json: { detail: 'Database unavailable' } });
    if (id) {
      const blud = state.bluds.find((item) => item.blud_id === id);
      return route.fulfill({
        status: blud ? 200 : 404,
        json: blud ?? { detail: 'Blud not found' },
      });
    }
    state.searches.push(url.search);
    const params = url.searchParams;
    const rows = state.bluds.filter(
      (item) =>
        item.archived === (params.get('archived') === 'true') &&
        (!params.get('q') ||
          `${item.name} ${item.owner_name}`.toLowerCase().includes(params.get('q')!.toLowerCase()))
    );
    const limit = Number(params.get('limit') ?? 25),
      offset = Number(params.get('offset') ?? 0);
    return route.fulfill({
      json: {
        bluds: rows.slice(offset, offset + limit),
        limit,
        offset,
        has_more: offset + limit < rows.length,
      },
    });
  });
  return state;
}

test('create from empty directory; failed save preserves required fields', async ({
  page,
  context,
}) => {
  await mockApi(context, member);
  const api = await bludsApi(context, []);
  await page.goto('/roster');
  await expect(page).toHaveURL(/\/bluds$/);
  await expect(page.getByRole('heading', { name: 'No Bluds yet' })).toBeVisible();
  await page.getByRole('button', { name: 'Add Blud' }).click();
  await expect(page.getByRole('button', { name: 'Create Blud' })).toBeDisabled();
  await page.getByLabel('Character name', { exact: true }).fill('Frostfern');
  await page.getByLabel('Class', { exact: true }).selectOption('mage');
  await page.getByLabel('Character creation date').fill('2026-10-28');
  api.error = 503;
  await page.getByRole('button', { name: 'Create Blud' }).click();
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(page.getByLabel('Character name', { exact: true })).toHaveValue('Frostfern');
  api.error = 0;
  await page.getByRole('button', { name: 'Create Blud' }).click();
  await expect(page).toHaveURL(/\/bluds\/20$/);
  await expect(page.getByRole('heading', { name: 'Frostfern', exact: true })).toBeVisible();
  expect(api.bluds[0].character_created_on).toBe('2026-10-28');
  expect(api.bluds[0].spec_id).toBeNull();
});

test('owner updates professions, farming, dungeons; archive and restore on a phone', async ({
  page,
  context,
}, info) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockApi(context, member);
  const api = await bludsApi(context);
  await page.goto('/bluds/10');
  await page.getByRole('button', { name: 'Edit details' }).click();
  await page.getByLabel('Farming zone', { exact: true }).selectOption('riverglades');
  await page.getByLabel('Spec', { exact: true }).selectOption('mage-frost');
  await page.getByRole('button', { name: 'Save details' }).click();
  await expect(page.getByRole('region', { name: 'Character details' })).toContainText(
    'Riverglades'
  );
  await page.getByRole('button', { name: 'Edit professions' }).click();
  await page.getByRole('checkbox', { name: 'Mining', exact: true }).check();
  await page.getByLabel('Mining level', { exact: true }).fill('120');
  await page.getByRole('checkbox', { name: 'Alchemy', exact: true }).check();
  await expect(page.getByRole('checkbox', { name: 'Tailoring', exact: true })).toBeDisabled();
  await page.getByRole('checkbox', { name: 'Cooking', exact: true }).check();
  await page.getByRole('button', { name: 'Save professions' }).click();
  await expect(page.getByRole('region', { name: 'Professions', exact: true })).toContainText(
    'Mining · 120'
  );
  await expect(page.getByRole('region', { name: 'Professions', exact: true })).toContainText(
    'Alchemy · Level not set'
  );
  await page.getByRole('region', { name: 'Dungeon progress' }).locator('summary').click();
  await page.getByLabel('Ragefire Chasm status', { exact: true }).selectOption('completed_rerun');
  await page.getByRole('button', { name: 'Save Ragefire Chasm status', exact: true }).click();
  await expect(page.getByText('1/2 dungeons completed', { exact: true })).toBeVisible();
  await expect(page.getByText('1 looking to rerun', { exact: true })).toBeVisible();
  await noOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath('bluds-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'Archive Blud' }).click();
  await expect(page.getByRole('alertdialog')).toContainText('All progress is retained');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect(api.bluds[0].archived).toBe(false);
  await page.getByRole('button', { name: 'Archive Blud' }).click();
  await page.getByRole('button', { name: 'Confirm archive' }).click();
  await expect(page.getByRole('button', { name: 'Restore Blud' })).toBeVisible();
  await page.getByRole('button', { name: 'Restore Blud' }).click();
  await expect(page.getByRole('button', { name: 'Archive Blud' })).toBeVisible();
  expect(api.bluds[0].completed_dungeons).toBe(1);
  await page.setViewportSize({ width: 320, height: 720 });
  await noOverflow(page);
});

test('dungeon disclosure preserves drafts and stays open after saving', async ({ page, context }) => {
  await mockApi(context, member);
  const api = await bludsApi(context);
  await page.goto('/bluds/10');
  const tracker = page.getByRole('region', { name: 'Dungeon progress' });
  const summary = tracker.locator('summary');
  const disclosure = tracker.locator('details');
  const status = page.getByLabel('Ragefire Chasm status', { exact: true });
  await expect(summary).toContainText('0/2 completed');
  await expect(status).toBeHidden();
  await summary.focus();
  await expect(summary).toBeFocused();
  await expect(summary).toHaveCSS('outline-style', 'solid');
  await expect(summary).toHaveCSS('outline-width', '2px');
  await summary.press('Enter');
  await expect(status).toBeVisible();
  await status.selectOption('completed');
  await summary.click();
  await expect(status).toBeHidden();
  await summary.press('Space');
  await expect(status).toHaveValue('completed');
  expect(api.writes).toBe(0);
  await page.getByRole('button', { name: 'Save Ragefire Chasm status', exact: true }).click();
  await expect(summary).toContainText('1/2 completed');
  await expect(disclosure).toHaveAttribute('open', '');
  await status.selectOption('completed_rerun');
  await page.getByRole('button', { name: 'Save Ragefire Chasm status', exact: true }).click();
  await expect(page.getByText('1 looking to rerun', { exact: true })).toBeVisible();
  await expect(summary).toContainText('1/2 completed');
  await summary.click();
  await expect(summary).toContainText('1/2 completed');
});

test('dungeon disclosure resets on reload and visits to either character', async ({ page, context }) => {
  await mockApi(context, member);
  await bludsApi(context, [original, { ...original, blud_id: 11, name: 'Riveralt' }]);
  await page.goto('/bluds/10');
  const tracker = page.getByRole('region', { name: 'Dungeon progress' });
  const summary = tracker.locator('summary');
  const disclosure = tracker.locator('details');
  await summary.click();
  await expect(disclosure).toHaveAttribute('open', '');
  await page.reload();
  await expect(summary).toBeVisible();
  await expect(disclosure).not.toHaveAttribute('open');
  await summary.click();
  await page.getByRole('link', { name: '← Bluds' }).click();
  await page.getByRole('link', { name: 'Riveralt', exact: true }).click();
  await expect(summary).toBeVisible();
  await expect(disclosure).not.toHaveAttribute('open');
  await summary.click();
  await page.goBack();
  await page.getByRole('link', { name: 'Riverfrost', exact: true }).click();
  await expect(summary).toBeVisible();
  await expect(disclosure).not.toHaveAttribute('open');
});

for (const width of [1280, 375, 320]) {
  test(`dungeon disclosure fits at ${width}px`, async ({ page, context }, info) => {
    await page.setViewportSize({ width, height: 812 });
    await mockApi(context, member);
    await bludsApi(context);
    await page.goto('/bluds/10');
    const summary = page.getByRole('region', { name: 'Dungeon progress' }).locator('summary');
    await expect(summary).toContainText('0/2 completed');
    await noOverflow(page);
    await page.screenshot({ path: info.outputPath(`dungeons-${width}-collapsed.png`), fullPage: true });
    await summary.click();
    await expect(page.getByLabel('Ragefire Chasm status', { exact: true })).toBeVisible();
    await noOverflow(page);
    await page.screenshot({ path: info.outputPath(`dungeons-${width}-expanded.png`), fullPage: true });
  });
}

test('combined filters and pagination live in URL; back link retains filters', async ({
  page,
  context,
}, info) => {
  await mockApi(context, member);
  const api = await bludsApi(context, [original, { ...original, blud_id: 11, name: 'Riveralt' }]);
  await page.goto('/bluds?limit=1');
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page).toHaveURL(/offset=1/);
  await page.getByRole('link', { name: 'Riveralt', exact: true }).click();
  await page.getByRole('link', { name: '← Bluds' }).click();
  await expect(page).toHaveURL(/offset=1/);
  await page.getByLabel('Search characters or members').fill('River');
  await page.getByLabel('Class filter').selectOption('mage');
  await page.getByLabel('Profession filter').selectOption('mining');
  await page.getByLabel('Farming zone filter').selectOption('westfall');
  await page.getByLabel('Dungeon filter').selectOption('ragefire-chasm');
  await page.getByLabel('Dungeon status filter').selectOption('completed_rerun');
  await page.getByRole('checkbox', { name: 'Mine only' }).check();
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page).not.toHaveURL(/offset=/);
  await expect.poll(() => api.searches.at(-1)).toContain('dungeon_status=completed_rerun');
  expect(api.searches.at(-1)).toContain('profession_id=mining');
  await page.screenshot({ path: info.outputPath('bluds-desktop.png'), fullPage: true });
  await page.getByLabel('Search characters or members').fill('absent');
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page.getByRole('heading', { name: 'No matching Bluds' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByRole('link', { name: 'Riverfrost', exact: true })).toBeVisible();
});

test('another member is read only; officer correction is explicit and permission loss removes it', async ({
  page,
  context,
}) => {
  const auth = await mockApi(context, { ...member, id: 2 });
  await bludsApi(context);
  await page.goto('/bluds/10');
  await expect(page.getByRole('heading', { name: 'Riverfrost', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Edit details' })).toHaveCount(0);
  await page.getByRole('region', { name: 'Dungeon progress' }).locator('summary').click();
  await expect(page.getByRole('heading', { name: 'Ragefire Chasm' })).toBeVisible();
  await expect(page.getByLabel('Ragefire Chasm status')).toHaveCount(0);
  auth.account = { ...officer(), id: 2 };
  await page.reload();
  await page.getByRole('button', { name: 'Correct this Blud' }).click();
  await expect(page.getByText('Officer correction:', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Edit details' }).click();
  await page.getByLabel('Character name', { exact: true }).fill('Corrected');
  await page.getByRole('button', { name: 'Save details' }).click();
  await expect(page.getByRole('heading', { name: 'Corrected', exact: true })).toBeVisible();
  auth.account = { ...member, id: 2 };
  await page.reload();
  await expect(page.getByRole('button', { name: 'Correct this Blud' })).toHaveCount(0);
});

test('missing resources, read errors, and capability gates', async ({ page, context }) => {
  const auth = await mockApi(context, member);
  const api = await bludsApi(context);
  await page.goto('/bluds/999');
  await expect(page.getByRole('heading', { name: 'Blud not found' })).toBeVisible();
  api.failReads = true;
  await page.goto('/bluds');
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  api.failReads = false;
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('link', { name: 'Riverfrost', exact: true })).toBeVisible();
  auth.account = { ...member, permissions: ['guild.read'] };
  await page.goto('/bluds/10');
  await expect(page).toHaveURL(/\/unauthorized$/);
});
