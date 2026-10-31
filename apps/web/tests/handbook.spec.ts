import { test, expect, type BrowserContext } from '@playwright/test';
import { mockApi, member, officer, noOverflow } from './fixtures';
import type { HandbookSection } from '../app/features/handbook/types';

const original: HandbookSection = {
  slug: 'scheduling',
  title: 'Scheduling expectations',
  body: 'Synthetic scheduling guidance.',
  revision: 1,
  updated_at: '2026-11-01T00:00:00Z',
  author_account_id: 1,
  author_name: 'River',
};

async function handbookApi(context: BrowserContext, sections: HandbookSection[] = []) {
  const state = {
    sections: [...sections],
    revisions: [...sections],
    error: 0,
    failReads: false,
    writes: 0,
    historyReads: 0,
  };
  await context.route('**/api/handbook**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const slug = url.pathname.split('/')[3];
    const method = request.method();
    if (method !== 'GET') {
      state.writes++;
      expect(request.headers()['x-csrf-protection']).toBe('1');
      if (state.error)
        return route.fulfill({
          status: state.error,
          json: {
            detail:
              state.error === 409
                ? 'A newer revision was saved. Keep a copy of your draft, then reload the latest section before editing again.'
                : 'Database unavailable',
          },
        });
      const body = request.postDataJSON();
      const current = state.sections.find((item) => item.slug === slug);
      const section: HandbookSection = {
        slug: slug ?? body.slug,
        title: body.title,
        body: body.body,
        revision: (current?.revision ?? 0) + 1,
        updated_at: '2026-11-01T01:00:00Z',
        author_account_id: 1,
        author_name: 'River',
      };
      if (method === 'PUT') {
        expect(Object.keys(body).sort()).toEqual(['body', 'expected_revision', 'title']);
        expect(body.expected_revision).toBe(current?.revision);
      }
      state.sections = [...state.sections.filter((item) => item.slug !== section.slug), section];
      state.revisions.unshift(section);
      return route.fulfill({ status: method === 'POST' ? 201 : 200, json: section });
    }
    if (state.failReads)
      return route.fulfill({ status: 503, json: { detail: 'Database unavailable' } });
    if (url.pathname.endsWith('/revisions')) {
      state.historyReads++;
      const offset = Number(url.searchParams.get('offset'));
      return route.fulfill({
        json: {
          revisions: state.revisions
            .filter((item) => item.slug === slug)
            .slice(offset, offset + 10),
          limit: 10,
          offset,
        },
      });
    }
    if (slug) {
      const section = state.sections.find((item) => item.slug === slug);
      return route.fulfill({
        status: section ? 200 : 404,
        json: section ?? { detail: 'Handbook section not found' },
      });
    }
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    return route.fulfill({
      json: {
        sections: state.sections.filter((item) =>
          `${item.title} ${item.body}`.toLowerCase().includes(q)
        ),
      },
    });
  });
  return state;
}

test('empty handbook lets officers create their own sections and keeps errors recoverable', async ({
  page,
  context,
}) => {
  await mockApi(context, officer());
  const api = await handbookApi(context);
  await page.goto('/handbook');
  await expect(page.getByRole('heading', { name: 'No handbook sections yet' })).toBeVisible();
  await page.getByRole('button', { name: 'Add section' }).click();
  await page.screenshot({
    path: test.info().outputPath('handbook-empty-create.png'),
    fullPage: true,
  });
  await page.getByLabel('URL slug').fill('own-policy');
  await page.getByLabel('Title', { exact: true }).fill('Our own policy');
  await page.getByLabel('Section text').fill('Officer-authored test text.');
  api.error = 503;
  await page.getByRole('button', { name: 'Create section', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(page.getByLabel('Section text')).toHaveValue('Officer-authored test text.');
  api.error = 0;
  await page.getByRole('button', { name: 'Create section', exact: true }).click();
  await expect(page).toHaveURL(/\/handbook\/own-policy$/);
  await expect(page.getByRole('heading', { name: 'Our own policy' })).toBeVisible();
  await expect(page.getByRole('article')).toHaveText('Officer-authored test text.');
  expect(api.writes).toBe(2);
});

test('members search, read safe plain text, and have no editor/history controls', async ({
  page,
  context,
}) => {
  await mockApi(context, member);
  const unsafe =
    '<img src=x onerror="window.handbookXss=true"><script>window.handbookXss=true</script>';
  const api = await handbookApi(context, [{ ...original, body: unsafe }]);
  await page.goto('/handbook');
  await expect(page.getByRole('button', { name: 'Add section' })).toHaveCount(0);
  await page.getByLabel('Search the handbook').fill('absent');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No matching sections' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear search' }).click();
  await page.getByRole('link', { name: original.title, exact: true }).click();
  await expect(page.getByRole('article')).toHaveText(unsafe);
  await expect(page.getByRole('article').locator('img, script')).toHaveCount(0);
  expect(await page.evaluate(() => 'handbookXss' in window)).toBe(false);
  await expect(page.getByRole('button', { name: 'Edit section' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'View revisions' })).toHaveCount(0);
  expect(api.historyReads).toBe(0);
});

test('officer edits keep immutable snapshots and show safe revision content', async ({
  page,
  context,
}) => {
  await mockApi(context, officer());
  await handbookApi(context, [original]);
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'Edit section' }).click();
  await expect(page.getByLabel('URL slug')).toHaveCount(0);
  await page.getByLabel('Section text').fill('<script>window.handbookXss=true</script>');
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByRole('status')).toContainText('Revision saved.');
  await page.getByRole('button', { name: 'View revisions' }).click();
  const history = page.getByRole('region', { name: 'Revision history' });
  await history.locator('summary').filter({ hasText: 'Revision 1:' }).click();
  await expect(history).toContainText(original.body);
  await history.locator('summary').filter({ hasText: 'Revision 2:' }).click();
  await expect(history).toContainText('<script>window.handbookXss=true</script>');
  await expect(history.locator('script')).toHaveCount(0);
  expect(await page.evaluate(() => 'handbookXss' in window)).toBe(false);
});

test('stale save retains the draft and reopens on latest version after cancel', async ({
  page,
  context,
}) => {
  await mockApi(context, officer());
  const api = await handbookApi(context, [original]);
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'Edit section' }).click();
  await page.getByLabel('Section text').fill('My unsaved draft');
  api.sections = [{ ...original, revision: 2, body: 'Another officer’s update' }];
  api.error = 409;
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByRole('alert')).toContainText('newer revision');
  await expect(page.getByLabel('Section text')).toHaveValue('My unsaved draft');
  await expect(page.getByRole('button', { name: 'Save revision' })).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Edit section' }).click();
  await expect(page.getByLabel('Section text')).toHaveValue('Another officer’s update');
  api.error = 0;
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByRole('status')).toContainText('Revision saved.');
});

test('write and background read failure preserve an officer draft', async ({ page, context }) => {
  await mockApi(context, officer());
  const api = await handbookApi(context, [original]);
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'Edit section' }).click();
  await page.getByLabel('Section text').fill('Draft during outage');
  api.error = 503;
  api.failReads = true;
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByLabel('Section text')).toHaveValue('Draft during outage');
  await expect(page.getByRole('button', { name: 'Save revision' })).toBeEnabled();
});

for (const width of [320, 375, 1280]) {
  test(`handbook create, edit, and history fit ${width}px`, async ({ page, context }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(context, officer());
    await handbookApi(context, [{ ...original, body: 'A'.repeat(250) }]);
    await page.goto('/handbook');
    await page.getByRole('button', { name: 'Add section' }).click();
    await noOverflow(page);
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.getByRole('link', { name: original.title, exact: true }).click();
    await page.getByRole('button', { name: 'Edit section' }).click();
    await page.getByRole('button', { name: 'View revisions' }).click();
    await page.locator('summary').click();
    await noOverflow(page);
    await page.screenshot({
      path: test.info().outputPath(`handbook-${width}.png`),
      fullPage: true,
    });
  });
}

test('event and material guidance links search officer-created sections', async ({
  page,
  context,
}) => {
  await mockApi(context, member);
  await handbookApi(context, [
    original,
    { ...original, slug: 'resources', title: 'Material handling' },
    { ...original, slug: 'drops', title: 'Loot policy' },
  ]);
  for (const [path, label, title] of [
    ['/events', 'Scheduling guidance', original.title],
    ['/events', 'Loot guidance', 'Loot policy'],
    ['/crafting', 'Material guidance', 'Material handling'],
  ]) {
    await page.goto(path);
    await page.getByRole('link', { name: label, exact: true }).click();
    await page.getByRole('link', { name: title, exact: true }).click();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  }
});

test('revision history paginates without losing the section', async ({ page, context }) => {
  await mockApi(context, officer());
  const latest = { ...original, revision: 12 };
  const api = await handbookApi(context, [latest]);
  api.revisions = Array.from({ length: 12 }, (_, index) => ({ ...original, revision: 12 - index }));
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'View revisions' }).click();
  await expect(page.locator('summary')).toHaveCount(10);
  await page.getByRole('button', { name: 'Older revisions' }).click();
  await expect(page.locator('summary')).toHaveCount(2);
  await expect(page.locator('summary').first()).toContainText('Revision 2:');
  await expect(page.getByRole('button', { name: 'Older revisions' })).toBeDisabled();
  await page.getByRole('button', { name: 'Newer revisions' }).click();
  await expect(page.locator('summary').first()).toContainText('Revision 12:');
});

test('read errors retry and missing sections provide a route back', async ({ page, context }) => {
  await mockApi(context, member);
  const api = await handbookApi(context, [original]);
  api.failReads = true;
  await page.goto('/handbook');
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  api.failReads = false;
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('link', { name: original.title, exact: true })).toBeVisible();
  await page.goto('/handbook/missing');
  await expect(page.getByRole('alert')).toContainText('Handbook section not found');
  await page.getByRole('link', { name: 'Back to handbook' }).click();
  await expect(page.getByRole('heading', { name: 'Guild Handbook', exact: true })).toBeVisible();
});
