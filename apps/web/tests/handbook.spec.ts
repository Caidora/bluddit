import { test, expect, type BrowserContext, type Locator } from '@playwright/test';
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

const markdown = [
  '## Raid guidance',
  '',
  '**Be prepared** and *be kind*. ~~Old policy~~',
  '',
  '- Bring supplies',
  '- [x] Read the rules',
  '- [ ] Sign up',
  '',
  '1. Arrive early',
  '2. Join voice',
  '',
  '> Ask an officer for help.',
  '',
  '[Scheduling](/handbook/scheduling) and https://example.com',
  '',
  '| Role | Time |',
  '| --- | --- |',
  '| Tank | 19:00 |',
  '',
  '`inline code`',
  '',
  '```text',
  'keep  these spaces',
  '```',
  '',
  '![Guild banner](/guild-banner.png)',
].join('\n');

async function expectMarkdown(content: Locator) {
  await expect(content.getByRole('heading', { name: 'Raid guidance' })).toHaveCount(1);
  await expect(content.locator('strong')).toHaveText('Be prepared');
  await expect(content.locator('em')).toHaveText('be kind');
  await expect(content.locator('del')).toHaveText('Old policy');
  await expect(content.locator('ol li')).toHaveText(['Arrive early', 'Join voice']);
  await expect(content.locator('blockquote')).toContainText('Ask an officer');
  await expect(content.getByRole('link', { name: 'Scheduling' })).toHaveAttribute('href', '/handbook/scheduling');
  await expect(content.getByRole('link', { name: 'https://example.com' })).toHaveAttribute('href', 'https://example.com');
  await expect(content.getByRole('cell', { name: 'Tank', exact: true })).toHaveCount(1);
  await expect(content.locator('pre code')).toHaveText('keep  these spaces\n');
  await expect(content.getByRole('img', { name: 'Guild banner' })).toHaveAttribute('src', '/guild-banner.png');
  const tasks = content.getByRole('checkbox');
  await expect(tasks).toHaveCount(2);
  await expect(tasks.nth(0)).toBeChecked();
  await expect(tasks.nth(1)).not.toBeChecked();
  for (const task of await tasks.all()) await expect(task).toBeDisabled();
}

async function handbookApi(context: BrowserContext, sections: HandbookSection[] = []) {
  await context.route('**/guild-banner.png', (route) => route.fulfill({
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="200"><rect width="2400" height="200" fill="#ff784f"/></svg>',
  }));
  const state = {
    sections: [...sections],
    revisions: [...sections],
    error: 0,
    failReads: false,
    writes: 0,
    historyReads: 0,
    holdDelete: null as Promise<void> | null,
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
                ? method === 'DELETE'
                  ? 'A newer revision was saved. Reload and review the latest section before deleting again.'
                  : 'A newer revision was saved. Keep a copy of your draft, then reload the latest section before editing again.'
                : state.error === 404
                  ? 'Handbook section not found'
                : 'Database unavailable',
          },
        });
      const current = state.sections.find((item) => item.slug === slug);
      if (method === 'DELETE') {
        if (state.holdDelete) await state.holdDelete;
        if (!current)
          return route.fulfill({ status: 404, json: { detail: 'Handbook section not found' } });
        expect(Number(url.searchParams.get('expected_revision'))).toBe(current.revision);
        state.sections = state.sections.filter((item) => item.slug !== slug);
        state.revisions = state.revisions.filter((item) => item.slug !== slug);
        return route.fulfill({ status: 204 });
      }
      const body = request.postDataJSON();
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
  const source = '## Our guidance\n\n**Officer-authored** test text.';
  await page.getByLabel('Section text').fill(source);
  api.error = 503;
  await page.getByRole('button', { name: 'Create section', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  await expect(page.getByLabel('Section text')).toHaveValue(source);
  api.error = 0;
  await page.getByRole('button', { name: 'Create section', exact: true }).click();
  await expect(page).toHaveURL(/\/handbook\/own-policy$/);
  await expect(page.getByRole('heading', { name: 'Our own policy' })).toBeVisible();
  await expect(page.getByRole('article').getByRole('heading', { name: 'Our guidance' })).toBeVisible();
  await expect(page.getByRole('article').locator('strong')).toHaveText('Officer-authored');
  expect(api.sections[0].body).toBe(source);
  expect(api.writes).toBe(2);
});

test('members search, read inert HTML, and have no editor/history controls', async ({
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
  await expect(page.getByRole('button', { name: 'Delete section' })).toHaveCount(0);
  expect(api.historyReads).toBe(0);
});

test('Markdown renders consistently in excerpts, published sections, and immutable revisions', async ({ page, context }) => {
  await mockApi(context, officer());
  const api = await handbookApi(context, [{ ...original, body: markdown }]);
  await page.goto('/handbook');
  const excerpt = page.locator('.handbook-markdown-compact');
  await expectMarkdown(excerpt);
  await expect(excerpt.getByRole('heading')).toHaveCSS('font-size', '14px');
  expect(await excerpt.evaluate((element) => element.clientHeight)).toBeLessThanOrEqual(96);
  await page.screenshot({ path: test.info().outputPath('handbook-markdown-excerpt.png'), fullPage: true });
  await page.getByRole('link', { name: original.title, exact: true }).click();
  await expectMarkdown(page.getByRole('article'));
  await page.screenshot({ path: test.info().outputPath('handbook-markdown-section.png'), fullPage: true });
  await page.getByRole('button', { name: 'Edit section' }).click();
  await expect(page.getByLabel('Section text')).toHaveValue(markdown);
  await page.getByLabel('Section text').fill('## Updated guidance\n\n**New revision**');
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByRole('article').getByRole('heading', { name: 'Updated guidance' })).toBeVisible();
  expect(api.sections[0].body).toBe('## Updated guidance\n\n**New revision**');
  await page.getByRole('button', { name: 'View revisions' }).click();
  const previous = page.locator('details').filter({ hasText: 'Revision 1:' });
  await previous.locator('summary').click();
  await expectMarkdown(previous);
  expect(api.revisions.find((item) => item.revision === 1)?.body).toBe(markdown);
});

test('unsafe HTML and URL protocols remain inert on every Markdown surface', async ({ page, context }) => {
  await mockApi(context, officer());
  const unsafe = [
    '<img src=x onerror="window.handbookXss=true"><script>window.handbookXss=true</script>',
    '',
    '[Unsafe link](javascript:alert%281%29)',
    '',
    '![Unsafe image](data:image/svg+xml;base64,PHN2Zy8+)',
  ].join('\n');
  await handbookApi(context, [{ ...original, body: unsafe }]);
  async function expectSafe(content: Locator) {
    await expect(content).toContainText('<script>window.handbookXss=true</script>');
    await expect(content.locator('script, img[onerror]')).toHaveCount(0);
    await expect(content.getByRole('link', { name: 'Unsafe link' })).toHaveAttribute('href', '');
    await expect(content.getByRole('img', { name: 'Unsafe image' })).not.toHaveAttribute('src', /^(data|javascript):/);
    expect(await page.evaluate(() => 'handbookXss' in window)).toBe(false);
  }
  await page.goto('/handbook');
  await expectSafe(page.locator('.handbook-markdown'));
  await page.getByRole('link', { name: original.title, exact: true }).click();
  await expectSafe(page.getByRole('article'));
  await page.getByRole('button', { name: 'View revisions' }).click();
  await page.locator('summary').click();
  await expectSafe(page.locator('details'));
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
    const wideBody = `${markdown}\n\n[${'A'.repeat(250)}](https://example.com)\n\n| ${'Wide column | '.repeat(12)}\n| ${'--- | '.repeat(12)}\n| ${'Long content | '.repeat(12)}\n\n\`\`\`text\n${'long-code-'.repeat(100)}\n\`\`\``;
    await handbookApi(context, [{ ...original, body: wideBody }]);
    await page.goto('/handbook');
    await page.getByRole('button', { name: 'Add section' }).click();
    await noOverflow(page);
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.getByRole('link', { name: original.title, exact: true }).click();
    await expect(page.getByRole('article').getByRole('img')).toBeVisible();
    const wideTable = page.getByRole('article').getByRole('region', { name: 'Scrollable table' }).last();
    expect(await wideTable.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
    const wideCode = page.getByRole('article').locator('pre').last();
    expect(await wideCode.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
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

for (const width of [320, 1280]) {
  test(`officer confirms permanent deletion with keyboard at ${width}px`, async ({ page, context }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockApi(context, officer());
    const api = await handbookApi(context, [original]);
    await page.goto('/handbook?q=scheduling');
    await page.getByRole('link', { name: original.title, exact: true }).click();
    await page.getByRole('button', { name: 'View revisions' }).click();
    await expect(page.locator('summary')).toHaveCount(1);
    await page.getByRole('button', { name: 'Edit section' }).click();
    await expect(page.getByRole('button', { name: 'Delete section' })).toBeDisabled();
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.getByRole('button', { name: 'Delete section' }).focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('alertdialog');
    await expect(dialog).toContainText(original.title);
    await expect(dialog).toContainText('all its revision history');
    await noOverflow(page);
    await page.screenshot({ path: test.info().outputPath(`delete-section-${width}.png`) });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    expect(api.writes).toBe(0);
    await page.getByRole('button', { name: 'Delete section' }).click();
    let release!: () => void;
    api.holdDelete = new Promise<void>((resolve) => { release = resolve; });
    await dialog.getByRole('button', { name: 'Permanently delete' }).click();
    await expect(dialog.getByRole('button', { name: 'Deleting…' })).toBeDisabled();
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeVisible();
    release();
    await expect(page).toHaveURL(/\/handbook$/);
    await expect(page.getByRole('status')).toContainText('Section deleted.');
    await expect(page.getByRole('heading', { name: 'No handbook sections yet' })).toBeVisible();
    expect(api.writes).toBe(1);
    expect(api.revisions).toEqual([]);
    await page.getByLabel('Search the handbook').fill('scheduling');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'No matching sections' })).toBeVisible();
    await page.goto('/handbook/scheduling');
    await expect(page.getByRole('alert')).toContainText('Handbook section not found');
  });
}

test('deletion failure is retryable and stale deletion requires reload and fresh confirmation', async ({ page, context }) => {
  await mockApi(context, officer());
  const api = await handbookApi(context, [original]);
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'Delete section' }).click();
  const dialog = page.getByRole('alertdialog');
  api.error = 503;
  await dialog.getByRole('button', { name: 'Permanently delete' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Database unavailable');
  await expect(dialog.getByRole('button', { name: 'Permanently delete' })).toBeEnabled();
  api.error = 409;
  api.sections = [{ ...original, revision: 2, title: 'Updated scheduling' }];
  await dialog.getByRole('button', { name: 'Permanently delete' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Reload and review');
  await expect(dialog.getByRole('button', { name: 'Permanently delete' })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('button', { name: 'Delete section' })).toBeDisabled();
  await page.getByRole('button', { name: 'Reload section' }).click();
  await expect(page.getByRole('heading', { name: 'Updated scheduling', exact: true })).toBeVisible();
  api.error = 0;
  await page.getByRole('button', { name: 'Delete section' }).click();
  await expect(dialog).toContainText('Updated scheduling');
  await dialog.getByRole('button', { name: 'Permanently delete' }).click();
  await expect(page).toHaveURL(/\/handbook$/);
  expect(api.writes).toBe(3);
});

test('section already deleted elsewhere offers return to handbook', async ({ page, context }) => {
  await mockApi(context, officer());
  const api = await handbookApi(context, [original]);
  await page.goto('/handbook/scheduling');
  await page.getByRole('button', { name: 'Delete section' }).click();
  api.sections = [];
  await page.getByRole('button', { name: 'Permanently delete' }).click();
  const dialog = page.getByRole('alertdialog');
  await expect(dialog.getByRole('alert')).toContainText('Handbook section not found');
  await dialog.getByRole('button', { name: 'Back to handbook' }).click();
  await expect(page).toHaveURL(/\/handbook$/);
  await expect(page.getByRole('heading', { name: 'No handbook sections yet' })).toBeVisible();
});
