---
layout: "kb.njk"
kicker: "Reference"
status: "Living reference · Runtimes, transport and data security"
scope: "What encoding, compiling, sandboxes, TLS and containers each protect, and the gaps between them, from SVG files to SAP."
markdownUrl: "/docs/machine-code-rust-wasm.md"
sourceUrl: "https://github.com/persephonepunch/game11ty/blob/main/src/pages/runtime-boundaries.md"
updated: "2026-10-13"
ogImage: "/docs/og-runtime-boundaries.jpg"
heroImage: "/docs/runtime-boundaries-hero.jpg"
heroCaption: "Top of the diagram. <a href=\"/docs/svg-base64-security-gaps.svg\">Open the full SVG</a> · <a href=\"/docs/svg-base64-security-gaps.jpg\">JPG</a>."
summary: "Base64, a Rust compile, a Wasm sandbox, TLS and a container each protect one thing, and people assume they protect more. This reference pairs them up: machine code, Rust and Wasm (what actually runs), SVG and native code (a document that can act like a program), and server and client (where a rule is really enforced). It ends with 31 gaps and the control that closes each."
ogImageAlt: "Diagram: one SVG traveling as base64 and the three ways it can be displayed, four definitions (base64, compile, machine code, bare metal), what each layer checks from browser to Rust service, and TLS hops in Next.js hydration and a CRM to Shopify data bus"
permalink: "/machine-code-rust-wasm/"
title: "Machine Code/Rust/WASM, SVG/Native, Server/Client"
description: "What base64, Rust, WebAssembly, SVG, TLS, containers and server-side rules each protect for PII, PCI and PHI data, and the 31 gaps between them."
templateEngineOverride: md
---
Every layer in a modern stack protects one thing. Base64 makes bytes safe to paste as text. A compiler turns a program into one that runs. A sandbox limits what code can reach. TLS protects the wire. None of them decides who can read the data, and that is where most gaps live.

The title pairs the ideas this article compares:

- **Machine Code / Rust / WASM:** what actually runs, and how much a compiler or sandbox can promise about it.
- **SVG / Native:** an SVG is a document that can behave like a program; native code is a program with no document to hide behind.
- **Server / Client:** where a rule is really enforced, and where it's only a suggestion.

**Diagram:** [Open the full SVG](/docs/svg-base64-security-gaps.svg) (1600 × 4290) · [JPG](/docs/svg-base64-security-gaps.jpg). Numbers in the dashed circles match the gap list at the end.

<figure class="gate-fig">
  <a href="/docs/svg-base64-security-gaps.svg"><img src="/docs/svg-base64-security-gaps.svg" width="1600" height="4290" loading="lazy" style="display:block;width:100%;height:auto;border:1px solid var(--g3);background:#fff" alt="The full diagram, top to bottom: one SVG with a hidden script and patient metadata, the same file as a base64 data URI, and the three ways a page can display it; definitions of base64, compile, machine code and bare metal; what each layer checks and misses from browser and Elm through TLS, Cloudflare, Xano and a Rust service; TLS hops in Next.js hydration and a CRM-to-Shopify data bus; JVM, iPaaS and Wasm stacks compared on isolation, network access, memory safety, supply chain, patching, Consent Mode v2 and idempotency; VM, Docker and Kubernetes isolation and transport; and 31 numbered security gaps, each with a fix."></a>
  <figcaption>The full diagram, displayed with &lt;img&gt; so its SVG can't run code on this page (gap 3). <a href="/docs/svg-base64-security-gaps.svg">Open the SVG</a> · <a href="/docs/svg-base64-security-gaps.jpg">JPG</a>.</figcaption>
</figure>

**Companion article:** [ALT, XMP and Favicons](/article/), on how descriptions and rights travel inside media files.

## Four words that get confused

| Term | What it is | Reversible? | Security value |
| --- | --- | --- | --- |
| Base64 | An encoding: any bytes rewritten as 64 text characters | Yes, by anyone, in one line | None. It changes the alphabet, not who can read it |
| Compile | Source translated into a different program: Rust to machine code or Wasm, Elm to JavaScript | No: comments and names are gone | The compiler can refuse unsafe programs (Rust) or runtime exceptions (Elm) |
| Machine code | The binary instructions a CPU runs: an opcode plus operands, specific to one chip family. `48 89 E5` is `mov rbp, rsp` on x86-64 | Disassembles back to readable instructions (objdump, Ghidra) | None by itself. Compiled is not hidden |
| Bare metal | Code running straight on the hardware with no operating system: firmware, bootloaders, microcontrollers | — | No OS to contain a bug, so memory safety and signed firmware carry the weight |

Base64 and machine code both look unreadable. Neither is secret.

## SVG is a document that can run code

An SVG is XML. Besides shapes, it can hold `<script>`, `onload=` handlers, `<foreignObject>` with embedded HTML, links to outside files, and text and metadata that carry names and IDs. Base64-encoding it into a `data:` URI keeps every one of those, about 33% larger, and hides `<script` from any filter that only reads text.

How the page displays it decides whether that code runs:

| How it's displayed | Script runs? | Risk |
| --- | --- | --- |
| `<img src="data:image/svg+xml;base64,…">` | No | Text and metadata are still readable |
| Inline `<svg>` or `el.innerHTML = atob(b64)` | Yes, on your origin | Cookies, tokens and any PHI on the page |
| `<object>`, `<iframe>`, or opening the `.svg` URL | Yes, in the file's origin | Same-origin uploads become cross-site scripting |

Treat untrusted SVG as code: decode it, sanitize it (DOMPurify or svgo, removing script, `on*` handlers, `foreignObject` and outside links), display it with `<img>`, and serve uploads from a separate asset domain with `Content-Security-Policy: sandbox`. Treat an exported chart as the data it shows: an SVG of patient results is PHI.

Native code has the opposite problem. A parser written in C that reads an untrusted image or 3D file can be exploited through a memory bug. That is why this site's GLB parser is a `no_std` Rust crate with no `unsafe` code ([firmware/glb-parse](https://github.com/persephonepunch/game11ty/tree/main/firmware/glb-parse)).

## Rust and Elm turn rules into compile errors

Rust's ownership rules mean every value has one owner, and passing it moves it. That makes a consent check something the compiler enforces:

```rust
pub fn send_to_ads(data: Pii<Email>, grant: ConsentGrant) -> Result<(), Error> { /* … */ }

let grant = consent::verify(&req)?;   // the only way to get one
send_to_ads(email, grant)?;
send_to_ads(other_email, grant)?;     // compile error: use of moved value `grant`
```

- **Single use:** a `ConsentGrant` is consumed by the send, so one consent can't cover two exports.
- **No accidental logging:** a `Pii<T>` wrapper whose `Debug` prints `[REDACTED]` and that doesn't implement `Serialize` can't end up in a log line or a JSON response.
- **Read versus write:** a function that takes `&PatientRecord` can't change it; only `&mut` can, and only one at a time.

Elm gets similar guarantees differently. Functions are pure, so a view that renders patient data can't send it anywhere. Opaque types decide in one module what any screen may show. [Ports](https://guide.elm-lang.org/interop/ports.html) are the only exit to JavaScript, which gives you one list to audit, and Elm packages can't contain JavaScript.

Both guarantees hold inside one program. Types force a check to happen; they can't prove the check is the right one.

## WebAssembly limits reach, not readership

A Wasm module gets its own linear memory and can only call the functions its host gives it. [Shopify Functions](https://shopify.dev/docs/api/functions) take this further: Rust compiled to Wasm, a GraphQL query in, a list of operations out, no network, no files and an instruction limit. A Cloudflare Worker runs in its own V8 isolate and reaches the network only through `fetch`.

That makes Wasm a strong place to run rules. It doesn't make data private: whatever the module is handed, it can read, and the sandbox is only as tight as the host imports ([WebAssembly security](https://webassembly.org/docs/security/)).

## Server versus client

The browser is untrusted. Anyone can edit the compiled JavaScript or call your API directly, so a rule enforced only in client code, in Elm or React, protects your users from your bugs, not your server from attackers.

| Layer | What it checks | What it doesn't |
| --- | --- | --- |
| Browser · Elm | Pure views can't fetch; ports are the only exit; opaque types mask PII | A user editing the JS or calling the API directly |
| TLS | Encrypts in transit; proves the server's identity | Data at rest; data at the edge |
| Cloudflare edge | CORS for other sites' browser reads; WAF patterns; a consent egress gate in a Worker | curl, servers or AI agents; payloads inside base64; plaintext at Cloudflare |
| TLS [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/) | Re-encrypts to the origin and validates its certificate | Anything, in Flexible mode: that's plain HTTP to the origin |
| Xano | Auth token on every call; per-record preconditions; field encryption if built | Scrubbing request history; sanitizing SVG uploads |
| Rust service | Memory safety; single-use consent grants; redacted PII types | Whether the rule itself is right |

CORS is a browser rule, not access control. The only layer that stops an unauthorized caller is server-side authorization that checks each record.

Next.js blurs the line. Server Components fetch data on the first request, before a consent banner has loaded. The props they return are serialized into the HTML and the RSC payload, where they outlive TLS in View Source, saved pages and caches. Any variable prefixed `NEXT_PUBLIC_` is [compiled into the client bundle](https://nextjs.org/docs/app/guides/environment-variables).

## TLS is hop by hop

Each arrow in a pipeline is its own TLS session, and the data is plaintext inside every box. Anything stored, cached, logged or rendered there is outside TLS's protection.

**Next.js server render to client hydration:** browser request → CDN edge (TLS ends; HTML may be cached) → Next server (fetches on request) → Shopify or Xano API (server-to-server call, request logs) → browser hydration (props readable in the page).

**CRM to Shopify cloud data bus:** CRM in Xano → queue or webhook table (payload stored at rest) → Cloudflare Worker (Admin token from KV) → Shopify Admin API → Shopify webhook back (verify the HMAC on the raw body).

For a data bus, sign each message (HMAC or Ed25519), encrypt sensitive fields end to end, and use mTLS between services, so a decrypting hop can't read or alter what it forwards.

## Three stacks for the same data

The same products, customers, consent and conversions can move through very different runtimes.

| Concern | JVM: SFCC · Salesforce · MuleSoft | iPaaS: SAP · Azure · Celigo · Magento | Wasm: Shopify Functions · Workers |
| --- | --- | --- | --- |
| Isolation | Shared JVM process; quotas and governor limits | Vendor tenancy: your data on the iPaaS platform | Own memory per module; a V8 isolate per Worker |
| Network access | Any library in the process can connect out | Flows reach every connected system's API | Functions: none. Workers: fetch via the host |
| Memory safety | Garbage-collected; secrets in Strings can't be wiped | PHP and ABAP are memory-safe; the risk is configuration | Can't touch host memory; Rust ownership inside |
| Supply chain | Large JAR trees; Log4Shell (2021) | Magento extensions and checkout JavaScript (Magecart) | Small modules; risk sits in the host imports |
| Who patches | Salesforce; you, for self-hosted Mule | You: SAP Notes, Magento patches. The iPaaS vendor for its platform | Shopify and Cloudflare; you rebuild the module |
| Consent Mode v2 | Must survive every DataWeave map and batch job | The ERP has no consent field: map it or lose it | Captured at the storefront, checked at the edge |
| Idempotency | Mule Idempotent Message Validator | [Service Bus duplicate detection](https://learn.microsoft.com/en-us/azure/service-bus-messaging/duplicate-detection); IDoc numbers | Event ID deduped in a Durable Object |

The JVM no longer has an in-process sandbox: the Security Manager was deprecated in Java 17 ([JEP 411](https://openjdk.org/jeps/411)), so every dependency runs with the application's full rights. SAP itself can run on AWS, Azure or Google Cloud, so a stack like this one may cross clouds, adding a TLS hop and a data-residency question at each crossing.

[Consent Mode v2](https://developers.google.com/tag-platform/security/guides/consent) and idempotency are data rules, not runtime features. Every stack has to carry the consent state (`ad_user_data`, `ad_personalization` and the storage signals) and a stable idempotency key with every event, or retries create duplicates and audiences reach Google without consent.

## VM, Docker and Kubernetes

| Concern | Virtual machine | Docker | Kubernetes |
| --- | --- | --- | --- |
| The wall | A hypervisor; each guest has its own kernel | One shared host kernel: namespaces, cgroups, seccomp | Docker's wall on each node, plus RBAC on the API |
| Escape needs | A hypervisor bug: rare | A kernel bug, `--privileged`, or a mounted `docker.sock` | Any container escape, or a token with broad RBAC |
| Traffic by default | Over the VPC; not always encrypted | Host bridge network, plaintext between containers | A flat network: any pod reaches any pod, in plaintext |
| Encrypt in transit | TLS, WireGuard or IPsec | TLS inside each app; host root can still sniff | An mTLS service mesh, or WireGuard in the CNI |
| Secrets | Cloud KMS or a vault | Never in ENV or image layers; [build secrets](https://docs.docker.com/build/building/secrets/) | [Secrets are base64](https://kubernetes.io/docs/concepts/configuration/secret/) in etcd until you [turn on encryption](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/) |
| Data in memory | The host can read it, unless it's a confidential VM | Host root and any privileged container | The node, and anyone allowed to exec into the pod |

A VM is the stronger wall and a container is the faster one. Neither encrypts data on the wire. Lock down pod traffic with a default-deny [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/) and encrypt it with mTLS or WireGuard. Use confidential VMs (AMD SEV-SNP, Intel TDX) where PHI or card data must stay hidden even from the cloud host.

## 31 gaps and the control that closes each

| # | Gap | Fix |
| --- | --- | --- |
| 1 | Base64 is not encryption | Encrypt or tokenize; never base64 a secret, key, token or card number |
| 2 | Encoding hides payloads from filters | Decode first, then sanitize |
| 3 | SVG executes when inlined | Display with `<img>`; CSP sandbox; a separate asset domain |
| 4 | CORS is not access control | Server-side authorization per record; deny by default |
| 5 | The edge sees plaintext | Full (strict); a BAA before PHI; field-level encryption |
| 6 | Logs keep what they're sent | Scrub fields or disable body logging; redacting types |
| 7 | SVG carries data, not just pixels | Strip metadata; classify an export as the data it shows |
| 8 | The client is untrusted | Enforce every rule again on the server |
| 9 | Compiled is not hidden | Secrets stay on the server; ship only scoped, short-lived tokens |
| 10 | Hydration ships data into the page | Pass only what the screen needs; fetch PII after consent |
| 11 | Shared caches mix customers | `Cache-Control: private, no-store` on personalized routes |
| 12 | Server fetch runs before consent | Gate server fetches on the consent cookie |
| 13 | `NEXT_PUBLIC_` compiles into the bundle | Secrets server-only; scan the built bundle in CI |
| 14 | TLS is hop by hop on a data bus | Sign messages; encrypt fields end to end; mTLS |
| 15 | Unverified or replayed webhooks | Verify the HMAC on the raw body; reject stale events |
| 16 | Queue rows outlive the message | Store IDs, not payloads; purge processed rows |
| 17 | Admin tokens at the edge | Least-privilege scopes, short lifetimes, rotation |
| 18 | Middleware sees everything | Mask fields in transforms; turn off payload logging |
| 19 | The JVM has no in-process sandbox | Isolate services; scan dependencies; patch fast |
| 20 | Consent isn't carried with the event | Attach Consent Mode v2 state at capture; drop when denied |
| 21 | Retries duplicate writes | One idempotency key per event; upsert on stable IDs |
| 22 | Wasm host imports are the door | Grant the fewest imports possible |
| 23 | Containers share the kernel | Non-root, dropped capabilities, seccomp; a VM for untrusted code |
| 24 | Kubernetes Secrets are base64 | etcd encryption with a KMS provider, or an external vault |
| 25 | Pod traffic is plaintext by default | Default-deny NetworkPolicy; mTLS or WireGuard |
| 26 | Secrets baked into images | Build secrets; image scanning; inject at runtime |
| 27 | The host can read VM memory | Confidential VMs; keys in an HSM or KMS |
| 28 | The iPaaS keeps copies | Mask fields in the flow; short retention; confirm region and DPA |
| 29 | Integration credentials are too broad | Least privilege per interface; managed identity; rotation |
| 30 | Checkout JavaScript gets skimmed | Patch; CSP and Subresource Integrity; PCI DSS 4.0 script inventory |
| 31 | Batch files sit in plaintext | PGP-encrypt; delete after pickup; prefer APIs or queues |

Base64 changes how data is written, not who can read it. Compiling changes what code can do. TLS protects the wire, not the endpoints, and sandboxes limit reach, not readership. Only encryption, server-side authorization and contracts decide who can read the data.

## Sources

- MDN: [SVG `<script>` element](https://developer.mozilla.org/en-US/docs/Web/SVG/Element/script)
- OWASP: [Cross-Site Scripting Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- The Rust Book: [What is ownership?](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html)
- Elm Guide: [Ports](https://guide.elm-lang.org/interop/ports.html)
- WebAssembly: [Security](https://webassembly.org/docs/security/)
- Shopify: [Functions](https://shopify.dev/docs/api/functions)
- Cloudflare: [Full (strict) SSL mode](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
- Next.js: [Environment variables](https://nextjs.org/docs/app/guides/environment-variables)
- Google: [Consent mode](https://developers.google.com/tag-platform/security/guides/consent)
- OpenJDK: [JEP 411, deprecate the Security Manager](https://openjdk.org/jeps/411)
- Microsoft: [Service Bus duplicate detection](https://learn.microsoft.com/en-us/azure/service-bus-messaging/duplicate-detection)
- Kubernetes: [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/), [encrypting data at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/), [network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- Docker: [Build secrets](https://docs.docker.com/build/building/secrets/)
