// Local stand-ins for the egress gate, for `wrangler dev` only. One Worker
// plays three parts so a refusal can be watched end to end:
//   /entries  the ledger (Xano in production): POST records, GET lists, 409 on a repeated key
//   /check    the claims check: any actor containing "revoked" is inactive
//   /vendor/* a fake model vendor: counts every byte it receives
// State lives in memory and resets when the Worker reloads, or on POST /reset.
let ledger = [], received = []

export default {
  async fetch(request) {
    const { pathname } = new URL(request.url)
    const post = request.method === "POST"

    if (pathname === "/entries" && post) {
      const entry = await request.json()
      if (entry.idempotency_key && ledger.some((e) => e.idempotency_key === entry.idempotency_key)) return new Response("duplicate", { status: 409 })
      ledger.push(entry)
      console.log(`ledger  ${entry.decision}${entry.reason ? ` (${entry.reason})` : ""}  ${entry.data_class}  ${entry.destination}`)
      return new Response("recorded", { status: 201 })
    }
    if (pathname === "/entries") return Response.json(ledger)

    if (pathname === "/check" && post) {
      const { actor = "" } = await request.json()
      return Response.json({ active: !actor.includes("revoked") })
    }

    if (pathname.startsWith("/vendor/") && post) {
      const bytes = (await request.arrayBuffer()).byteLength
      received.push({ path: pathname, bytes, at: new Date().toISOString() })
      console.log(`vendor  received ${bytes} bytes at ${pathname}`)
      return Response.json({ ok: true })
    }
    if (pathname === "/vendor") return Response.json({ requests: received.length, bytes: received.reduce((t, r) => t + r.bytes, 0), received })

    if (pathname === "/reset" && post) { ledger = []; received = []; return new Response("reset") }
    return new Response("not found", { status: 404 })
  },
}
