// SB-15: a higher-order head function. It wraps any fetch handler and returns
// a hardened response, so security never depends on a theme's <head>.
// Tested in Cloudflare's runtime by test/head.test.mjs.

// Browser security mechanisms that are deprecated or removed. An origin that
// still sends them is relying on a model browsers no longer honour, so they
// are stripped and replaced by the server-set headers below.
const DEPRECATED = ["x-xss-protection", "expect-ct", "public-key-pins", "public-key-pins-report-only", "feature-policy"]

export const withHead = (handler) => async (request, env, ctx) => {
  let res
  try {
    res = await handler(request, env, ctx)
  } catch {
    // Fail closed: a hardened, generic error. Internal details never leak.
    res = new Response("Bad gateway", { status: 502, headers: { "content-type": "text/plain; charset=utf-8" } })
  }
  // Fail closed: an origin error page may carry stack traces or internal
  // paths, so any 5xx body is replaced with a generic one (status kept).
  if (res.status >= 500) {
    res = new Response("Server error", { status: res.status, headers: { "content-type": "text/plain; charset=utf-8" } })
  }
  const out = new Response(res.body, res)
  for (const h of DEPRECATED) out.headers.delete(h)

  const nonce = crypto.randomUUID().replaceAll("-", "")
  out.headers.set("Content-Security-Policy", `default-src 'self'; script-src 'self' 'nonce-${nonce}'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`)
  out.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
  out.headers.set("X-Content-Type-Options", "nosniff")
  out.headers.set("Referrer-Policy", "strict-origin-when-cross-origin")

  // Media types are case-insensitive: TEXT/HTML is still HTML.
  if (!(out.headers.get("content-type") || "").toLowerCase().includes("text/html")) return out
  return new HTMLRewriter()
    .on("head", { element(el) {
      el.append(`<script src="/embed/stack-loader.js" nonce="${nonce}"></script>`, { html: true })
    } })
    .transform(out)
}

export default { fetch: withHead((request) => fetch(request)) }
