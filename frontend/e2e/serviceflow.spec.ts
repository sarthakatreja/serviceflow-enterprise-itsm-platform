import { readFile } from 'node:fs/promises'
import { expect, test, type Page } from '@playwright/test'

type DemoRole = 'Administrator' | 'Employee' | 'Technician'

function navigation(page: Page, label: string) {
  return page.getByRole('navigation', { name: 'Workspace navigation' }).getByRole('link', { name: label, exact: true })
}

async function openDemo(page: Page, role: DemoRole) {
  await page.goto('/')
  await page.getByRole('button', { name: role, exact: true }).click()
  await expect(page.getByRole('heading', { name: role === 'Administrator' ? 'Service desk overview' : 'My service desk' })).toBeVisible()
}

async function createTicket(page: Page, title: string) {
  await navigation(page, 'Create ticket').click()
  await page.getByRole('textbox', { name: 'Title', exact: true }).fill(title)
  await page.getByRole('textbox', { name: /^Description/ }).fill('The shared laptop loses its Wi-Fi connection during a meeting.')
  await page.getByRole('combobox', { name: 'Category' }).selectOption('network')
  await page.getByRole('button', { name: 'Submit ticket' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  await expect(page.getByText('Ticket created.', { exact: true })).toBeVisible()
  return new URL(page.url()).pathname
}

async function setStatus(page: Page, status: string, notes?: string) {
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption(status)
  if (notes !== undefined) await page.getByRole('textbox', { name: /^Resolution notes/ }).fill(notes)
  await page.getByRole('button', { name: 'Save status and notes' }).click()
  await expect(page.getByText('Status and resolution notes saved.', { exact: true })).toBeVisible()
}

test('administrator can sign in and sign out', async ({ page }) => {
  await openDemo(page, 'Administrator')
  await expect(navigation(page, 'All tickets')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ticket activity' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to ServiceFlow' })).toBeVisible()
})

test('employee navigation and restricted administration routes honour the role', async ({ page }) => {
  await openDemo(page, 'Employee')
  await expect(navigation(page, 'My tickets')).toBeVisible()
  await expect(navigation(page, 'All tickets')).toHaveCount(0)
  await expect(navigation(page, 'User management')).toHaveCount(0)
  await expect(navigation(page, 'Reports')).toHaveCount(0)
  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible()
})

test('employee creates a ticket that an admin assigns and a technician resolves twice', async ({ page, browser }) => {
  const title = 'Regression ticket for resolution history'
  const first = 'Replaced the wireless driver and verified the connection.'
  const second = 'Replaced the failing wireless card and verified stability.'
  await openDemo(page, 'Employee')
  await createTicket(page, title)
  await navigation(page, 'My tickets').click()
  await expect(page.getByRole('link', { name: title })).toBeVisible()

  const admin = await browser.newPage({ baseURL: new URL(page.url()).origin })
  await openDemo(admin, 'Administrator')
  await navigation(admin, 'All tickets').click()
  await admin.getByRole('link', { name: title }).click()
  await admin.getByRole('combobox', { name: 'Assigned technician' }).selectOption({ label: 'Nadia Patel' })
  await admin.getByRole('button', { name: 'Save assignment' }).click()
  await expect(admin.getByText('Assignment saved.', { exact: true })).toBeVisible()
  await admin.context().close()

  const technician = await browser.newPage({ baseURL: new URL(page.url()).origin })
  await openDemo(technician, 'Technician')
  await navigation(technician, 'My tickets').click()
  await technician.getByRole('link', { name: title }).click()
  await setStatus(technician, 'in_progress')
  await setStatus(technician, 'resolved', first)
  const history = technician.locator('.resolution-history')
  await expect(history.getByText(first, { exact: true })).toBeVisible()

  await technician.getByRole('combobox', { name: 'Status', exact: true }).selectOption('in_progress')
  await technician.getByRole('button', { name: 'Reopen ticket', exact: true }).click()
  await expect(technician.getByText('Ticket reopened.', { exact: true })).toBeVisible()
  await expect(technician.getByRole('textbox', { name: /^Resolution notes/ })).toHaveValue('')
  await expect(history.getByText(first, { exact: true })).toBeVisible()

  await technician.getByRole('combobox', { name: 'Status', exact: true }).selectOption('resolved')
  await expect(technician.getByRole('button', { name: 'Save status and notes' })).toBeDisabled()
  await setStatus(technician, 'resolved', second)
  await expect(history.locator('li')).toHaveCount(2)
  await expect(history.locator('li').first()).toContainText(second)
  await expect(history.locator('li').last()).toContainText(first)
  await technician.context().close()
})

test('a visible ticket refreshes SLA information without clearing a comment draft', async ({ page }) => {
  await page.clock.install()
  await openDemo(page, 'Employee')
  const path = await createTicket(page, 'Regression ticket for live SLA')
  const draft = page.getByRole('textbox', { name: 'Add a comment' })
  await draft.fill('Please check the logs from the meeting room.')
  const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === '/api' + path + '/sla' && response.ok())
  await page.clock.fastForward(30_000)
  await refreshed
  await expect(draft).toHaveValue('Please check the logs from the meeting room.')
})

test('administrator downloads the filtered report as CSV', async ({ page }) => {
  await openDemo(page, 'Administrator')
  await navigation(page, 'Reports').click()
  await expect(page.getByRole('heading', { name: 'Matching tickets' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Priority', exact: true }).selectOption('high')
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('resolved')
  await page.getByRole('button', { name: 'Apply filters' }).click()
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe('serviceflow-ticket-report.csv')
  const csv = await readFile(await download.path(), 'utf8')
  expect(csv).toContain('Recover access to shared calendar,email,high,resolved')
  const rows = csv.trim().split(/\r?\n/).slice(1)
  expect(rows.length).toBeGreaterThan(0)
  expect(rows.every(row => row.includes(',high,resolved,'))).toBe(true)
})
