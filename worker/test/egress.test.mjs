// SB-23 egress gate: adversarial tests in Cloudflare's runtime (workerd, via
// Miniflare). The outbound service is the network capture: it sees every byte
// the gate sends, so "refused" is proven as zero bytes, not a status code.
import { test, before, after, beforeEach } from "node:test"
import assert from "node:assert/strict"
import { Miniflare } from "miniflare"

// EGRESS_MODULE lets mutate.mjs point the suite at a deliberately broken copy.
const MODULE = process.env.EGRESS_MODULE || new URL("../egress.mjs", import.meta.url).pathname

// Clearly fake marker values: they can never be real customer data.
const CANARY = { card: "4242 4242 4242 4242", email: "canary+dh@example.com", name: "Zz Canary", reading: "38.9C Zz Canary" }

const POLICY = {
  maxBytes: 2048,
  tags: { sku: "none", ink_low: "none", note: "none", email: "pii", reading: "phi" },
  destinations: {
    "model.example": { allows: ["none", "pii"], baa: false, regions: ["US"] },
    "clinic-ai.example": { allows: ["none", "pii", "phi"], baa: true, regions: ["US"] },
    "cdn.example": { allows: ["none"], baa: false, regions: ["US", "EU"] },
  },
}

let sent, ledger, claims, ledgerDown
let mf
before(() => {
  mf = new Miniflare({
    modules: true, scriptPath: MODULE,
    bindings: { POLICY: JSON.stringify(POLICY) },
    outboundService: async (req) => { sent.push({ url: req.url, bytes: new Uint8Array(await req.arrayBuffer()) }); return new Response("ok") },
    serviceBindings: {
      LEDGER: async (req) => {
        if (ledgerDown) return new Response("down", { status: 500 })
        const e = await req.json()
        if (e.idempotency_key && ledger.some((x) => x.idempotency_key === e.idempotency_key)) return new Response("dup", { status: 409 })
        ledger.push(e)
        return new Response("ok", { status: 201 })
      },
      CLAIMS: async (req) => claims(await req.json()),
    },
  })
})
after(() => mf.dispose())
beforeEach(() => { sent = []; ledger = []; ledgerDown = false; claims = () => Response.json({ active: true }) })

let n = 0
const send = async (destination, payload, extra = {}) => {
  const body = { destination, region: "US", actor: "agent:reorder-bot", on_behalf_of: "user:42", idempotency_key: `k${++n}`, payload, ...extra }
  const r = await mf.dispatchFetch("https://gate.example/egress", { method: "POST", body: JSON.stringify(body) })
  return [r.status, await r.json()]
}
const bytesOut = () => sent.reduce((t, s) => t + s.bytes.byteLength, 0)

test("allow: a payload of tagged 'none' fields reaches the destination unchanged, and is recorded", async () => {
  const payload = { sku: "HX-CLOUD-III", ink_low: true }
  const [status, res] = await send("https://model.example/v1", payload)
  assert.equal(status, 200)
  assert.equal(sent.length, 1)
  assert.deepEqual(JSON.parse(new TextDecoder().decode(sent[0].bytes)), payload, "the gate must not rewrite allowed content")
  assert.equal(res.bytes_sent, sent[0].bytes.byteLength)
  assert.equal(ledger.length, 1)
  assert.equal(ledger[0].decision, "allowed")
})

test("DH-03 block: PHI to a destination with no BAA sends zero bytes and records one refusal", async () => {
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1", reading: CANARY.reading })
  assert.equal(status, 403)
  assert.equal(res.reason, "phi_without_baa")
  assert.equal(bytesOut(), 0, "no bytes may leave on a refusal")
  assert.equal(ledger.length, 1)
  assert.equal(ledger[0].decision, "refused")
  assert.equal(ledger[0].reason, "phi_without_baa")
  assert.equal(ledger[0].data_class, "phi")
})

test("allow: PHI to a destination with a BAA on file goes out", async () => {
  const [status] = await send("https://clinic-ai.example/v1", { reading: CANARY.reading })
  assert.equal(status, 200)
  assert.equal(sent.length, 1)
})

test("DH-02 evasion: a card number hidden in a 'none' field is PCI and never leaves", async () => {
  for (const card of [CANARY.card, "4242-4242-4242-4242", "4242424242424242"]) {
    sent = []
    const [status, res] = await send("https://clinic-ai.example/v1", { note: `please charge ${card} today` })
    assert.equal(status, 403, card)
    assert.equal(res.reason, "pci_never_leaves")
    assert.equal(bytesOut(), 0)
  }
})

test("allow: a 16-digit number that fails the Luhn check is not mistaken for a card", async () => {
  const [status, res] = await send("https://cdn.example/v1", { sku: "1234567812345678" })
  assert.equal(status, 200, JSON.stringify(res))
})

test("evasion: an email hidden in a 'none' field raises it to PII", async () => {
  const [status, res] = await send("https://cdn.example/v1", { note: `contact ${CANARY.email}` })
  assert.equal(status, 403)
  assert.equal(res.reason, "class_not_allowed")
  assert.equal(res.data_class, "pii")
  assert.equal(bytesOut(), 0)
})

test("fail-closed: an untagged field is refused, named, and nothing leaves", async () => {
  const [status, res] = await send("https://cdn.example/v1", { sku: "HX-1", shoe_size: "9" })
  assert.equal(status, 403)
  assert.equal(res.reason, "untagged_field:shoe_size")
  assert.equal(bytesOut(), 0)
  assert.equal(ledger[0].fields.shoe_size, "pci", "an untagged field is recorded as the most sensitive class")
  assert.equal(ledger[0].data_class, "pci")
})

test("fail-closed: a tag the gate doesn't know counts as untagged", async () => {
  const [status, res] = await send("https://cdn.example/v1", { sku: "x", constructor: "y" })
  assert.equal(status, 403)
  assert.match(res.reason, /^untagged_field/)
})

test("block: an unknown destination is refused", async () => {
  const [status, res] = await send("https://elsewhere.example/v1", { sku: "HX-1" })
  assert.equal(status, 403)
  assert.equal(res.reason, "unknown_destination")
  assert.equal(bytesOut(), 0)
})

test("block: a region the destination isn't allowed to serve is refused", async () => {
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" }, { region: "EU" })
  assert.equal(status, 403)
  assert.equal(res.reason, "residency")
  assert.equal(bytesOut(), 0)
})

test("DH-17 block: an inactive claim in the system of record is refused", async () => {
  claims = () => Response.json({ active: false })
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" })
  assert.equal(status, 403)
  assert.equal(res.reason, "claim_inactive")
  assert.equal(bytesOut(), 0)
  assert.equal(ledger[0].reason, "claim_inactive")
})

test("fail-closed: if the claims service is down, nothing leaves", async () => {
  claims = () => new Response("down", { status: 503 })
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" })
  assert.equal(status, 403)
  assert.equal(res.reason, "claim_unavailable")
  assert.equal(bytesOut(), 0)
})

test("evasion: an error status is a no, even if its body claims active", async () => {
  claims = () => Response.json({ active: true }, { status: 500 })
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" })
  assert.equal(status, 403)
  assert.equal(res.reason, "claim_unavailable")
  assert.equal(bytesOut(), 0)
})

test("fail-closed: an unreadable claims answer is not taken as a yes", async () => {
  claims = () => new Response("<html>maintenance</html>", { status: 200 })
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" })
  assert.equal(status, 403)
  assert.equal(res.reason, "claim_unavailable")
  assert.equal(bytesOut(), 0)
})

test("fail-closed: no unrecorded egress, so if the ledger is down an allowable payload still doesn't leave", async () => {
  ledgerDown = true
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" })
  assert.equal(status, 503)
  assert.equal(res.reason, "ledger_unavailable")
  assert.equal(bytesOut(), 0)
})

test("DH-12 race: a repeated idempotency key is refused and sends once", async () => {
  const [a] = await send("https://model.example/v1", { sku: "HX-1" }, { idempotency_key: "reorder:dev7:evt9" })
  const [b, res] = await send("https://model.example/v1", { sku: "HX-1" }, { idempotency_key: "reorder:dev7:evt9" })
  assert.equal(a, 200)
  assert.equal(b, 409)
  assert.equal(res.reason, "duplicate_key")
  assert.equal(sent.length, 1)
})

test("block: a request with no idempotency key or actor is refused", async () => {
  const [status, res] = await send("https://model.example/v1", { sku: "HX-1" }, { idempotency_key: "" })
  assert.equal(status, 403)
  assert.equal(res.reason, "missing_key_or_actor")
  assert.equal(bytesOut(), 0)
})

test("DH-05 canary: the ledger records classes and names, never the values", async () => {
  await send("https://model.example/v1", { email: CANARY.email, reading: CANARY.reading, note: CANARY.card })
  const all = JSON.stringify(ledger)
  for (const v of Object.values(CANARY)) assert.ok(!all.includes(v), `ledger leaked ${v}`)
  assert.ok(!all.includes("4242"), "ledger leaked part of the card number")
  assert.deepEqual(ledger[0].fields, { email: "pii", reading: "phi", note: "pci" })
})

test("boundary: exactly maxBytes is held and evaluated; one byte over is refused unread", async () => {
  const base = { destination: "https://model.example/v1", region: "US", actor: "a", idempotency_key: "kb", payload: { sku: "" } }
  const len = (b) => new TextEncoder().encode(JSON.stringify(b)).byteLength
  base.payload.sku = "x".repeat(POLICY.maxBytes - len(base))
  assert.equal(len(base), POLICY.maxBytes)
  let r = await mf.dispatchFetch("https://gate.example/", { method: "POST", body: JSON.stringify(base) })
  assert.equal(r.status, 200, "exactly at the limit must pass")
  base.payload.sku += "x"; base.idempotency_key = "kb2"
  r = await mf.dispatchFetch("https://gate.example/", { method: "POST", body: JSON.stringify(base) })
  assert.equal(r.status, 403)
  assert.equal((await r.json()).reason, "too_large")
  assert.equal(sent.length, 1)
})

test("fail-closed: malformed JSON is refused and recorded", async () => {
  const r = await mf.dispatchFetch("https://gate.example/", { method: "POST", body: "{not json" })
  assert.equal(r.status, 403)
  assert.equal((await r.json()).reason, "bad_json")
  assert.equal(ledger[0].reason, "bad_json")
  assert.equal(bytesOut(), 0)
})

test("block: only POST is accepted", async () => {
  const r = await mf.dispatchFetch("https://gate.example/")
  assert.equal(r.status, 405)
  assert.equal(bytesOut(), 0)
})
