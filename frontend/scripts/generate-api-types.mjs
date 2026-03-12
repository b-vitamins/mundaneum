import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoDir = resolve(frontendDir, '..')
const backendDir = resolve(repoDir, 'backend')
const generatedDir = resolve(frontendDir, 'src', 'api')
const schemaPath = resolve(frontendDir, '.generated-openapi.json')
const outputPath = resolve(generatedDir, 'generated.ts')

mkdirSync(generatedDir, { recursive: true })

const schemaJson = execFileSync(
  'poetry',
  [
    'run',
    'python',
    '-c',
    'import json; from app.main import app; print(json.dumps(app.openapi()))',
  ],
  {
    cwd: backendDir,
    encoding: 'utf-8',
    stdio: ['ignore', 'pipe', 'inherit'],
  }
)

writeFileSync(schemaPath, schemaJson, 'utf-8')

execFileSync(
  'npx',
  ['openapi-typescript', schemaPath, '-o', outputPath],
  {
    cwd: frontendDir,
    stdio: 'inherit',
  }
)

execFileSync('npx', ['prettier', '--write', outputPath], {
  cwd: frontendDir,
  stdio: 'inherit',
})

rmSync(schemaPath)
