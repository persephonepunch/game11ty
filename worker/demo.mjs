// Send a few payloads through the local egress gate and show what reached the
// fake vendor and what the ledger recorded. Needs `npm run dev:stubs` and
// `npm run dev` running.   node demo.mjs
const GATE = "http://localhost:8787", STUBS = "http://localhost:8790"
const MODEL = "http://localhost:8790/vendor/model"    // no BAA
const CLINIC = "http://127.0.0.1:8790/vendor/clinic"  // BAA on file
const run = Date.now()

const cases = [
  ["tagged 'none' fields to the model", MODEL, { sku: "HX-CLOUD-III", ink_low: true }],
  ["PHI canary to the model (no BAA)", MODEL, { reading: "38.9C Zz Canary" }],
  ["PHI canary to the clinic (BAA)", CLINIC, { reading: "38.9C Zz Canary" }],
  ["card number hidden in a note", CLINIC, { note: "charge 4242 4242 4242 4242" }],
  ["untagged field", MODEL, { sku: "HX-1", shoe_size: "9" }],
  ["revoked actor", MODEL, { sku: "HX-1" }, { actor: "agent:revoked-bot" }],
]

await fetch(`${STUBS}/reset`, { method: "POST" })
for (const [i, [label, destination, payload, extra = {}]] of cases.entries()) {
  const body = { destination, region: "US", actor: "agent:reorder-bot", on_behalf_of: "user:42", idempotency_key: `demo:${run}:${i}`, payload, ...extra }
  const r = await fetch(GATE, { method: "POST", body: JSON.stringify(body) })
  const res = await r.json()
  console.log(`${String(r.status).padEnd(4)} ${res.decision.padEnd(8)} ${(res.reason || "").padEnd(24)} ${label}`)
}
const vendor = await (await fetch(`${STUBS}/vendor`)).json()
const ledger = await (await fetch(`${STUBS}/entries`)).json()
console.log(`\nvendor received ${vendor.requests} requests, ${vendor.bytes} bytes`)
console.log(`ledger holds ${ledger.length} entries: ${ledger.filter((e) => e.decision === "refused").length} refused, ${ledger.filter((e) => e.decision === "allowed").length} allowed`)
