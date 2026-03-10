import { execFileSync } from 'node:child_process'

execFileSync('npm', ['run', 'generate:api'], { stdio: 'inherit' })

try {
    execFileSync('git', ['diff', '--exit-code', '--', 'src/api/generated.ts'], {
        stdio: 'inherit',
    })
} catch {
    console.error('Generated API types are stale. Run `npm run generate:api` and commit the result.')
    process.exit(1)
}
