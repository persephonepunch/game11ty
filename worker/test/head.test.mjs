// SB-15 edge headers: adversarial tests for the higher-order head function,
// run in Cloudflare's real runtime (workerd, via Miniflare), not a stub.
import { test, before, after } from "node:test"
import assert from "node:assert/strict"
import { Miniflare } from "miniflare"

// HEAD_MODULE lets mutate.mjs point the suite at a deliberately broken copy.
const MODULE = process.env.HEAD_MODULE || new URL("../head.mjs", import.meta.url).pathname

let origin = () => new Response("ok")
let mf
before(() => {
  mf = new Miniflare({ modules: true, scriptPath: MODULE,
    outboundService: (req) => origin(req) })
})
after(() => mf.dispose())

const html = (body, headers = {}) => () =>
  new Response(`<!doctype html><html><head><title>t</title></head><body>${body}</body></html>`,
    { headers: { "content-type": "text/html; charset=utf-8", ...headers } })
const get = async (path = "/") => { const r = await mf.dispatchFetch(`https://site.example${path}`); return [r, await r.text()] }
const nonceOf = (csp) => /'nonce-([^']+)'/.exec(csp)?.[1]

test("allow: HTML gets a CSP nonce and the injected loader carries the same nonce", async () => {
  origin = html("<p>hi</p>")
  const [r, body] = await get()
  const nonce = nonceOf(r.headers.get("content-security-policy"))
  assert.ok(nonce, "CSP must carry a nonce")
  assert.match(body, new RegExp(`<script src="/embed/stack-loader.js" nonce="${nonce}"></script></head>`))
})

test("block: every response carries the baseline headers", async () => {
  origin = html("")
  const [r] = await get()
  assert.match(r.headers.get("strict-transport-security"), /max-age=31536000/)
  assert.equal(r.headers.get("x-content-type-options"), "nosniff")
  assert.match(r.headers.get("content-security-policy"), /frame-ancestors 'none'/)
  assert.equal(r.headers.get("referrer-policy"), "strict-origin-when-cross-origin")
})

test("block: the nonce is unique per request", async () => {
  origin = html("")
  const [a] = await get(), [b] = await get()
  assert.notEqual(nonceOf(a.headers.get("content-security-policy")), nonceOf(b.headers.get("content-security-policy")))
})

test("evasion: the origin cannot weaken the CSP", async () => {
  origin = html("", { "content-security-policy": "script-src * 'unsafe-inline'" })
  const [r] = await get()
  assert.doesNotMatch(r.headers.get("content-security-policy"), /unsafe-inline|script-src \*/)
})

test("evasion: an inline script from the origin never receives the nonce", async () => {
  origin = html("<script>steal()</script>")
  const [, body] = await get()
  assert.match(body, /<script>steal\(\)<\/script>/, "origin script must stay un-nonced so CSP blocks it")
})

test("evasion: an upper-case Content-Type is still treated as HTML", async () => {
  origin = () => new Response("<html><head></head><body></body></html>", { headers: { "content-type": "TEXT/HTML; charset=UTF-8" } })
  const [, body] = await get()
  assert.match(body, /stack-loader\.js/)
})

test("block: deprecated browser security headers are stripped, not trusted", async () => {
  origin = html("", { "x-xss-protection": "1; mode=block", "expect-ct": "max-age=0", "public-key-pins": "pin-sha256=\"x\"", "feature-policy": "camera 'none'" })
  const [r] = await get()
  for (const h of ["x-xss-protection", "expect-ct", "public-key-pins", "feature-policy"]) assert.equal(r.headers.get(h), null, h)
})

test("allow: non-HTML bodies are passed through byte-for-byte", async () => {
  const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 1, 2, 3])
  origin = () => new Response(bytes, { headers: { "content-type": "image/png" } })
  const r = await mf.dispatchFetch("https://site.example/a.png")
  assert.deepEqual(new Uint8Array(await r.arrayBuffer()), bytes)
  assert.equal(r.headers.get("x-content-type-options"), "nosniff")
})

test("fail-closed: an origin error still gets the baseline headers", async () => {
  origin = () => new Response("boom", { status: 500, headers: { "content-type": "text/html" } })
  const [r] = await get()
  assert.equal(r.status, 500)
  assert.ok(r.headers.get("content-security-policy"))
})

test("fail-closed: an origin error page never leaks its body", async () => {
  // Miniflare turns a thrown origin error into a 500 carrying the stack trace,
  // exactly the kind of page that must not reach a visitor.
  origin = () => { throw new Error("origin down at /srv/internal/path") }
  const [r, body] = await get()
  assert.ok(r.status >= 500)
  assert.ok(r.headers.get("content-security-policy"))
  assert.doesNotMatch(body, /origin down|internal|at /, "internal errors must not leak")
})

test("fail-closed: a handler that throws returns a hardened 502", async () => {
  // The catch path never reaches HTMLRewriter, so it runs in plain Node.
  const { withHead } = await import(MODULE)
  const r = await withHead(() => { throw new Error("secret detail") })(new Request("https://site.example/"))
  assert.equal(r.status, 502)
  assert.ok(r.headers.get("content-security-policy"))
  assert.doesNotMatch(await r.text(), /secret detail/)
})
