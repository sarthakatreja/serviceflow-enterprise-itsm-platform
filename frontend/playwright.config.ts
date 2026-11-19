import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const project = fileURLToPath(new URL('../', import.meta.url))
const port = process.env.SERVICEFLOW_E2E_PORT ?? '18011'
const origin = 'http://127.0.0.1:' + port
const windows = process.platform === 'win32'
const localPython = windows
  ? join(project, 'backend', '.venv', 'Scripts', 'python.exe')
  : join(project, 'backend', '.venv', 'bin', 'python')
const python = process.env.SERVICEFLOW_E2E_PYTHON ?? (existsSync(localPython) ? localPython : windows ? 'python' : 'python3')

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  use: { ...devices['Desktop Chrome'], baseURL: origin, trace: 'retain-on-failure' },
  webServer: {
    command: '"' + python + '" backend/tests/e2e_server.py',
    cwd: project,
    env: { SERVICEFLOW_E2E_PORT: port },
    url: origin + '/health',
    timeout: 30_000,
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 3_000 },
  },
})
