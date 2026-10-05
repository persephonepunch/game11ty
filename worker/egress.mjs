// SB-23: the egress gate. Every payload bound for a model or vendor is held,
// classified, evaluated and recorded before a single byte leaves. A refusal
// sends nothing and still leaves a ledger entry.
//
// Diagnosis and record, never repair: the gate does not rewrite, redact or
// shape a payload. Allowed content leaves exactly as the caller sent it;
// anything it can't allow is refused, and a person fixes the cause.
// Tested in Cloudflare's runtime by test/egress.test.mjs (DH-03 and friends).
//
// Bindings:
//   POLICY  JSON: { maxBytes, tags: {field: class}, destinations: {host: {allows, baa, regions}} }
//   LEDGER  service: POST an entry; 409 means the idempotency key already exists
//   CLAIMS  service: POST {actor, on_behalf_of, destination, data_class} -> {active}
// In production LEDGER and CLAIMS are the Xano system of record.

export const RANK = { none: 0, pii: 1, phi: 2, pci: 3 }
const MAX_BYTES = 64 * 1024

// Content that raises a field's class whatever its tag says.
const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i
const DIGIT_RUN = /\d(?:[ -]?\d){12,18}/g

export const luhn = (digits) => {
  let sum = 0
  for (let i = 0; i < digits.length; i++) {
    let d = +digits[digits.length - 1 - i]
    if (i % 2) { d *= 2; if (d > 9) d -= 9 }
    sum += d
  }
  return sum % 10 === 0
}
const hasCard = (text) => (text.match(DIGIT_RUN) || []).some((run) => luhn(run.replace(/\D/g, "")))

// 2. Classify. An untagged field, or a tag the gate doesn't know, counts as
// the most sensitive class until someone tags it.
export function classify(payload, tags) {
  const fields = {}
  let dataClass = "none"
  for (const [name, value] of Object.entries(payload)) {
    const tagged = Object.hasOwn(tags, name) && Object.hasOwn(RANK, tags[name])
    let cls = tagged ? tags[name] : "pci"
    const text = typeof value === "string" ? value : JSON.stringify(value)
    if (hasCard(text)) cls = "pci"
    else if (EMAIL.test(text) && RANK[cls] < RANK.pii) cls = "pii"
    fields[name] = { class: cls, tagged }
    if (RANK[cls] > RANK[dataClass]) dataClass = cls
  }
  return { fields, dataClass }
}

// 3. Evaluate against the destination registry. Returns a refusal reason, or null.
export function evaluate({ destination, region }, { fields, dataClass }, policy) {
  const untagged = Object.keys(fields).filter((n) => !fields[n].tagged)
  if (untagged.length) return `untagged_field:${untagged.join(",")}`
  let host
  try { host = new URL(destination).host } catch { return "bad_destination" }
  const d = policy.destinations?.[host]
  if (!d) return "unknown_destination"
  if (dataClass === "pci") return "pci_never_leaves"
  if (dataClass === "phi" && !d.baa) return "phi_without_baa"
  if (!(d.allows || []).includes(dataClass)) return "class_not_allowed"
  if (!(d.regions || []).includes(region)) return "residency"
  return null
}

const reply = (status, body) => Response.json(body, { status })

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return reply(405, { decision: "refused", reason: "method", bytes_sent: 0 })
    const policy = JSON.parse(env.POLICY)

    // 1. Hold: the whole body is buffered here; nothing streams onward.
    const raw = new Uint8Array(await request.arrayBuffer())
    let body = {}, reason = null
    if (raw.byteLength > (policy.maxBytes ?? MAX_BYTES)) reason = "too_large"
    else {
      try { body = JSON.parse(new TextDecoder().decode(raw)) } catch { reason = "bad_json" }
    }
    const { destination, region, actor, on_behalf_of, idempotency_key } = body
    const payload = body.payload && typeof body.payload === "object" ? body.payload : {}
    if (!reason && (!idempotency_key || !actor)) reason = "missing_key_or_actor"

    const c = classify(payload, policy.tags ?? {})
    reason ??= evaluate({ destination, region }, c, policy)

    // A live check in the system of record: is this actor allowed, right now?
    if (!reason) {
      try {
        const r = await env.CLAIMS.fetch("https://claims/check", { method: "POST",
          body: JSON.stringify({ actor, on_behalf_of, destination, data_class: c.dataClass }) })
        if (!r.ok) reason = "claim_unavailable"
        else if (!(await r.json()).active) reason = "claim_inactive"
      } catch { reason = "claim_unavailable" }  // unreadable answer: fail closed
    }

    // 5. Record first, allowed or refused. Field names and classes only,
    // never values: the ledger is long-lived, so it holds no payload content.
    const bytes = new TextEncoder().encode(JSON.stringify(payload))
    const entry = {
      idempotency_key: idempotency_key ?? null, actor: actor ?? null, on_behalf_of: on_behalf_of ?? null,
      destination: destination ?? null, region: region ?? null, data_class: c.dataClass,
      fields: Object.fromEntries(Object.entries(c.fields).map(([n, f]) => [n, f.class])),
      decision: reason ? "refused" : "allowed", reason, bytes: bytes.byteLength,
      occurred_at: new Date().toISOString(),
    }
    let recorded
    try { recorded = (await env.LEDGER.fetch("https://ledger/entries", { method: "POST", body: JSON.stringify(entry) })).status }
    catch { recorded = 0 }
    if (recorded === 409) return reply(409, { decision: "refused", reason: "duplicate_key", bytes_sent: 0 })
    // No unrecorded egress: if the decision can't be recorded, nothing leaves.
    if (recorded < 200 || recorded > 299) return reply(503, { decision: "refused", reason: "ledger_unavailable", bytes_sent: 0 })

    // 4. Decide. Refused: the held bytes are dropped here.
    if (reason) return reply(403, { decision: "refused", reason, data_class: c.dataClass, bytes_sent: 0 })
    const out = await fetch(destination, { method: "POST", headers: { "content-type": "application/json" }, body: bytes })
    return reply(200, { decision: "allowed", data_class: c.dataClass, bytes_sent: bytes.byteLength, status: out.status })
  },
}
