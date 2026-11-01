import { test, expect } from '@playwright/test';
import { login, member, mockApi } from './fixtures';

for (const timezoneId of ['Pacific/Auckland', 'Australia/Sydney', 'Australia/Perth']) {
  test(`event scheduling and viewer date in ${timezoneId}`, async ({ browser }, testInfo) => {
    test.skip(!process.env.TEST_DATABASE_URL, 'Requires the disposable real API fixture.');
    const context = await browser.newContext({
      timezoneId,
      locale: 'en-NZ',
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    try {
      await login(page, 'browser_gm', 'browser-only-password');
      await expect(page.getByRole('heading', { name: 'Welcome, Browser GM' })).toBeVisible();
      await page.goto('/events/new');
      await page.getByLabel('Title', { exact: true }).fill(`Regional run ${timezoneId}`);
      await page
        .getByRole('combobox', { name: 'Scheduling timezone', exact: true })
        .selectOption('Pacific/Auckland');
      await page.getByLabel('Local start date and time').fill('2026-11-01T00:30');
      await expect(page.getByRole('status')).toContainText('Scheduled:');
      await page
        .getByRole('combobox', { name: 'Dungeon destination', exact: true })
        .selectOption('ragefire-chasm');
      if (timezoneId === 'Pacific/Auckland') {
        let fail = true;
        await page.route('**/api/events', (route) => {
          if (route.request().method() === 'POST' && fail) {
            fail = false;
            return route.fulfill({ status: 503, json: { detail: 'Database unavailable' } });
          }
          return route.continue();
        });
        await page.getByRole('button', { name: 'Create event', exact: true }).click();
        await expect(page.getByRole('alert')).toContainText('Database unavailable');
        await expect(page.getByLabel('Title', { exact: true })).toHaveValue(
          `Regional run ${timezoneId}`
        );
      }
      await page.getByRole('button', { name: 'Create event', exact: true }).click();
      await expect(
        page.getByRole('heading', { name: `Regional run ${timezoneId}` })
      ).toBeVisible();
      const times = page.getByRole('region', { name: 'Event details' }).locator('time');
      await expect(times.first()).toContainText(timezoneId);
      await expect(times.first()).toContainText(
        timezoneId === 'Pacific/Auckland' ? '1 November 2026' : '31 October 2026'
      );
      await expect(times.nth(1)).toContainText('Pacific/Auckland');
      await page.getByRole('link', { name: 'Edit event', exact: true }).click();
      await expect(page.getByLabel('Local start date and time')).toHaveValue(
        '2026-11-01T00:30'
      );
      await page.getByLabel('Title', { exact: true }).fill(`Updated ${timezoneId}`);
      await page.getByRole('button', { name: 'Save event', exact: true }).click();
      await expect(page.getByRole('heading', { name: `Updated ${timezoneId}` })).toBeVisible();
      await page.reload();
      await expect(page.getByRole('heading', { name: `Updated ${timezoneId}` })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath('event-mobile.png'), fullPage: true });
      await expect(
        page.getByRole('link', { name: 'Ragefire Chasm: Bluds with incomplete progress' })
      ).toHaveAttribute(
        'href',
        '/bluds?dungeon_id=ragefire-chasm&dungeon_status=not_completed'
      );
      await page
        .getByRole('link', { name: 'Ragefire Chasm: Bluds with incomplete progress' })
        .click();
      await expect(page.getByLabel('Dungeon filter')).toHaveValue('ragefire-chasm');
      await page.goBack();
      await page.getByRole('button', { name: 'Cancel event', exact: true }).click();
      await page.getByRole('button', { name: 'Confirm cancellation' }).click();
      await expect(
        page
          .getByRole('region', { name: 'Event details' })
          .getByText('Cancelled', { exact: true })
      ).toBeVisible();
      await expect(page.getByRole('link', { name: 'Edit event', exact: true })).toHaveCount(0);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      ).toBe(true);
    } finally {
      await context.close();
    }
  });
}

test('DST gaps, both repeated choices, and changing scheduling clears the selection', async ({
  page,
}) => {
  test.skip(!process.env.TEST_DATABASE_URL, 'Requires the disposable real API fixture.');
  await login(page, 'browser_gm', 'browser-only-password');
  await expect(page.getByRole('heading', { name: 'Welcome, Browser GM' })).toBeVisible();
  await page.goto('/events/new');
  await page.getByLabel('Title', { exact: true }).fill('DST run');
  await page
    .getByRole('combobox', { name: 'Scheduling timezone', exact: true })
    .selectOption('Pacific/Auckland');
  await page.getByLabel('Local start date and time').fill('2026-09-27T02:30');
  await expect(page.getByRole('alert')).toContainText('does not exist');
  await expect(page.getByRole('button', { name: 'Create event', exact: true })).toBeDisabled();
  await page.getByLabel('Local start date and time').fill('2026-04-05T02:30');
  await expect(page.getByText('This time occurs twice. Choose an occurrence.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create event', exact: true })).toBeDisabled();
  await page.getByRole('radio', { name: /Earlier/ }).check();
  await expect(page.getByRole('status')).toContainText('UTC+13:00');
  await page.getByRole('radio', { name: /Later/ }).check();
  await expect(page.getByRole('status')).toContainText('UTC+12:00');
  await page
    .getByRole('combobox', { name: 'Scheduling timezone', exact: true })
    .selectOption('Australia/Sydney');
  await expect(page.getByRole('radio', { name: /Later/ })).not.toBeChecked();
  await page.getByRole('radio', { name: /Later/ }).check();
  await page.getByRole('button', { name: 'Create event', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'DST run', exact: true })).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Event details' }).locator('time').first()
  ).toHaveAttribute('datetime', '2026-04-04T16:30:00Z');
});

test('event list empty and retry states preserve filters', async ({ page, context }) => {
  await mockApi(context, {
    ...member,
    permissions: [...member.permissions, 'events.create', 'events.manage'],
  });
  let fail = true;
  await context.route('**/api/events?*', (route) =>
    route.fulfill({
      status: fail ? 503 : 200,
      json: fail
        ? { detail: 'Database unavailable' }
        : { events: [], offset: 0, limit: 25, has_more: false },
    })
  );
  await page.goto('/events?period=past&mine=true');
  await expect(page.getByRole('alert')).toContainText('Database unavailable');
  fail = false;
  await page.getByRole('button', { name: /retry|try again/i }).click();
  await expect(page.getByRole('heading', { name: 'No matching events' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'When', exact: true })).toHaveValue('past');
  await expect(page.getByLabel('Organized by me')).toBeChecked();
});
