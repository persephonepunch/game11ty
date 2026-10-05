// Mutation check for the Worker: break one rule at a time in a copy of the
// module and require its test suite to fail. A survivor is a missing test.
//   node mutate.mjs
import { readFileSync, writeFileSync, rmSync } from "node:fs"
import { spawnSync } from "node:child_process"

const TARGETS = [
  { rule: "SB-15", file: "head.mjs", env: "HEAD_MODULE", test: "test/head.test.mjs", mutants: [
    ["nonce missing from the injected loader", ' nonce="${nonce}"></script>', "></script>"],
    ["CSP header not set", 'out.headers.set("Content-Security-Policy"', 'out.headers.set("X-Unused"'],
    ["HSTS not set", 'out.headers.set("Strict-Transport-Security"', 'out.headers.set("X-Unused-2"'],
    ["deprecated headers kept", "for (const h of DEPRECATED) out.headers.delete(h)", ""],
    ["Content-Type compared case-sensitively", ".toLowerCase().includes", ".includes"],
    ["5xx bodies passed through", "if (res.status >= 500) {", "if (false) {"],
    ["handler errors not caught", "} catch {", "} catch (e) { throw e"],
    ["same nonce every request", 'crypto.randomUUID().replaceAll("-", "")', '"fixednonce"'],
  ] },
  { rule: "SB-23", file: "egress.mjs", env: "EGRESS_MODULE", test: "test/egress.test.mjs", mutants: [
    ["refused payloads still sent", 'if (reason) return reply(403,', "if (false) return reply(403,"],
    ["untagged fields treated as safe", 'let cls = tagged ? tags[name] : "pci"', 'let cls = tagged ? tags[name] : "none"'],
    ["untagged fields not refused", "if (untagged.length) return", "if (false) return"],
    ["card scan removed", 'if (hasCard(text)) cls = "pci"', 'if (false) cls = "pci"'],
    ["Luhn check skipped", "some((run) => luhn(run.replace(/\\D/g, \"\")))", "some(() => true)"],
    ["email scan removed", "else if (EMAIL.test(text) && RANK[cls] < RANK.pii)", "else if (false)"],
    ["PHI allowed without a BAA", 'if (dataClass === "phi" && !d.baa)', "if (false)"],
    ["PCI allowed out", 'if (dataClass === "pci") return "pci_never_leaves"', ""],
    ["unknown destinations allowed", 'if (!d) return "unknown_destination"', 'if (!d) return null'],
    ["residency not checked", 'if (!(d.regions || []).includes(region)) return "residency"', ""],
    ["claim check skipped", 'else if (!(await r.json()).active) reason = "claim_inactive"', ""],
    ["claims outage treated as allowed", 'if (!r.ok) reason = "claim_unavailable"', 'if (false) reason = "claim_unavailable"'],
    ["unreadable claims answer treated as allowed", '} catch { reason = "claim_unavailable" }', "} catch {}"],
    ["ledger outage ignored", "if (recorded < 200 || recorded > 299) return", "if (false) return"],
    ["duplicate keys sent again", "if (recorded === 409)", "if (false)"],
    ["size limit removed", 'reason = "too_large"', "reason = null"],
    ["missing key or actor allowed", "if (!reason && (!idempotency_key || !actor))", "if (false)"],
    ["payload values written to the ledger", "Object.entries(c.fields).map(([n, f]) => [n, f.class])", "Object.entries(payload)"],
  ] },
]

let survivors = 0, total = 0
for (const { rule, file, env, test, mutants } of TARGETS) {
  const source = readFileSync(new URL(`./${file}`, import.meta.url), "utf8")
  for (const [what, from, to] of mutants) {
    total++
    if (!source.includes(from)) { console.log(`STALE    ${rule}  ${what}`); survivors++; continue }
    const path = new URL(`./.mutant-${file}`, import.meta.url).pathname
    writeFileSync(path, source.replace(from, to))
    const r = spawnSync(process.execPath, ["--test", test], { env: { ...process.env, [env]: path }, encoding: "utf8" })
    rmSync(path)
    const killed = r.status !== 0
    if (!killed) survivors++
    console.log(`${killed ? "killed  " : "SURVIVED"} ${rule}  ${what}`)
  }
}
console.log(`\n${total - survivors}/${total} mutants killed`)
process.exit(survivors ? 1 : 0)
