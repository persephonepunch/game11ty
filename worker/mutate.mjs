// Mutation check for the head function: break one rule at a time in a copy of
// head.mjs and require the test suite to fail. A survivor is a missing test.
//   node mutate.mjs
import { readFileSync, writeFileSync, rmSync } from "node:fs"
import { spawnSync } from "node:child_process"

const SOURCE = readFileSync(new URL("./head.mjs", import.meta.url), "utf8")
const MUTANTS = [
  ["nonce missing from the injected loader", ' nonce="${nonce}"></script>', "></script>"],
  ["CSP header not set", 'out.headers.set("Content-Security-Policy"', 'out.headers.set("X-Unused"'],
  ["HSTS not set", 'out.headers.set("Strict-Transport-Security"', 'out.headers.set("X-Unused-2"'],
  ["deprecated headers kept", "for (const h of DEPRECATED) out.headers.delete(h)", ""],
  ["Content-Type compared case-sensitively", ".toLowerCase().includes", ".includes"],
  ["5xx bodies passed through", "if (res.status >= 500) {", "if (false) {"],
  ["handler errors not caught", "} catch {", "} catch (e) { throw e"],
  ["same nonce every request", 'crypto.randomUUID().replaceAll("-", "")', '"fixednonce"'],
]
let survivors = 0
for (const [what, from, to] of MUTANTS) {
  if (!SOURCE.includes(from)) { console.log(`STALE    ${what}`); survivors++; continue }
  const path = new URL("./.mutant-head.mjs", import.meta.url).pathname
  writeFileSync(path, SOURCE.replace(from, to))
  const r = spawnSync(process.execPath, ["--test"], { env: { ...process.env, HEAD_MODULE: path }, encoding: "utf8" })
  rmSync(path)
  const killed = r.status !== 0
  if (!killed) survivors++
  console.log(`${killed ? "killed  " : "SURVIVED"} SB-15  ${what}`)
}
console.log(`\n${MUTANTS.length - survivors}/${MUTANTS.length} mutants killed`)
process.exit(survivors ? 1 : 0)
