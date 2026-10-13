---
layout: "kb.njk"
kicker: "Illustration"
status: "Living reference · Diagram and gap index"
scope: "One page that maps SVG, base64, Rust, Elm, TLS, runtimes and containers to the 31 security gaps between them."
markdownUrl: "/docs/svg-rust-elm.md"
sourceUrl: "https://github.com/persephonepunch/game11ty/blob/main/src/pages/svg-rust-elm.md"
updated: "2026-10-13"
ogImage: "/docs/og-runtime-boundaries.jpg"
summary: "A single diagram that follows one SVG file from source to base64 to the browser, then through an Elm client, TLS, Cloudflare, Xano and a Rust service, two TLS pipelines, three integration stacks and three kinds of isolation. Dashed lines mark the gaps, and each numbered circle points to one of 31 gaps. This page shows the diagram, explains how to read it and indexes where every gap appears."
ogImageAlt: "Diagram: one SVG traveling as base64 and the three ways it can be displayed, four definitions (base64, compile, machine code, bare metal), what each layer checks from browser to Rust service, and TLS hops in Next.js hydration and a CRM to Shopify data bus"
heroImage: "/docs/svg-base64-security-gaps.svg"
heroWidth: 1600
heroHeight: 4290
heroAlt: "The full diagram, top to bottom: one SVG with a hidden script and patient metadata, the same file as a base64 data URI, and the three ways a page can display it; definitions of base64, compile, machine code and bare metal; what each layer checks and misses from browser and Elm through TLS, Cloudflare, Xano and a Rust service; TLS hops in Next.js hydration and a CRM-to-Shopify data bus; JVM, iPaaS and Wasm stacks compared on isolation, network access, memory safety, supply chain, patching, Consent Mode v2 and idempotency; VM, Docker and Kubernetes isolation and transport; and 31 numbered security gaps, each with a fix."
heroCaption: "The full illustration (1600 × 4290), displayed with &lt;img&gt; so its SVG can't run code on this page (gap 3). <a href=\"/docs/svg-base64-security-gaps.svg\">Open the SVG</a> · <a href=\"/docs/svg-base64-security-gaps.jpg\">JPG</a>."
permalink: "/svg-rust-elm/"
title: "SVG/Rust/Elm: The Security Gaps Illustration"
description: "A one-page diagram of where SVG, base64, Rust, Elm, TLS, JVM, iPaaS and Wasm runtimes, VMs and containers leave PII, PCI and PHI data exposed, with an index of 31 gaps."
templateEngineOverride: md
---
This illustration puts a whole data path on one page: one SVG file, the client that displays it, every server it passes through, and the runtimes and containers underneath. It is built to answer one question at each step: **who can read the data here?**

The reasoning behind each box, and the fix for every gap, is in the companion article, [Machine Code/Rust/WASM, SVG/Native, Server/Client](/machine-code-rust-wasm/).

## How to read it

| Mark | Meaning |
| --- | --- |
| Solid box | A step where data passes through and a control holds |
| Dashed box | A gap: data is stored, cached or exposed there, or code can run |
| Dashed circle with a number | Points to one of the 31 gaps listed at the bottom of the diagram |
| Dashed arrow | Traffic that is plaintext by default (between Kubernetes pods) |
| Grey arrow labeled TLS | One TLS session. The data is decrypted in the box at each end |
| "decrypts here" | Inside this box the data is plaintext, whatever the arrows say |

The diagram reads top to bottom in seven bands, each building on the one above.

## The seven bands

**1. One SVG, three ways in.** The source file holds a hidden `<script>` and patient details in `<metadata>`. Base64 turns it into a `data:` URI without changing any of it. How a page displays it decides whether the script runs: never through `<img>`, always when inlined or loaded in `<object>` or `<iframe>`.

**2. Four words that get confused.** Base64 (an encoding), compile (a translation into a new program), machine code (what the CPU runs) and bare metal (code with no operating system underneath). Only compiling changes what code can do. Bare metal is dashed because a memory bug there takes over the whole device.

**3. The request path.** Six boxes from the Elm client to a Rust service, each split into what it checks and what it doesn't. This is where the Elm and Rust guarantees sit, and where their limits show.

**4. TLS protects each hop, not the data.** Two pipelines, labeled A and B: a Next.js server render followed by client-side hydration, and a CRM-to-Shopify data bus. Every box decrypts.

**5. Same data, three stacks.** Lanes C, D and E carry the same products, customers and consent through a JVM stack (Salesforce, MuleSoft, Salesforce Commerce Cloud), an iPaaS stack (SAP, Azure, Celigo, Magento) and a Wasm stack (Shopify Functions, Cloudflare Workers). A table compares them on seven concerns, including Consent Mode v2 and idempotency.

**6. Isolation and transport.** Where the wall sits in a virtual machine, a Docker container and a Kubernetes cluster, and how data crosses between them.

**7. The gaps.** All 31 gaps, each with its fix.

## Where SVG, Rust and Elm appear

**SVG** is both the subject and the medium. Band 1 shows an SVG as a carrier of code and data (gaps 3 and 7), and the diagram itself is an SVG, which is why this page displays it with `<img>`. Gap 30 returns to it: card skimmers on Magento checkouts have been hidden in SVG `onload` attributes.

**Elm** is the first box of the request path ([An Introduction to Elm](https://guide.elm-lang.org/)). Its pure views, opaque types and ports keep a well-written client from leaking data by accident, but the box's "does not" side is gap 8: the browser is untrusted, so every rule has to be enforced again on the server.

**Rust** appears three times. Each idea links to the chapter of [The Rust Book](https://doc.rust-lang.org/book/) that explains it:

- **The Rust service** at the end of the request path: memory safety with no [`unsafe`](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html), a `ConsentGrant` that is consumed on use ([ownership](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html)), read-only versus exclusive access ([references and borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html)), and a `Pii<T>` type that redacts itself in logs and refuses to serialize.
- **Bare metal:** [`#![no_std]`](https://docs.rust-embedded.org/book/intro/no-std.html) (The Embedded Rust Book) and the site's own [GLB parser](https://github.com/persephonepunch/game11ty/tree/main/firmware/glb-parse), where memory safety is the only wall.
- **The Shopify Function** in lane E: [Rust compiled to Wasm](https://shopify.dev/docs/apps/build/functions/programming-languages/rust-for-functions), with no network access (gap 22 covers the host imports that remain).

Both languages share the same limit, shown on the Rust box: types can force a check to happen, but they can't prove the check is the right one.

## Gap index

Where each numbered circle appears in the diagram. Fixes are in the [companion article](/machine-code-rust-wasm/#31-gaps-and-the-control-that-closes-each) and at the bottom of the illustration.

| # | Gap | Where it appears |
| --- | --- | --- |
| 1 | Base64 is not encryption | Band 1, base64 data URI |
| 2 | Encoding hides payloads from filters | Band 1, base64 data URI; Cloudflare edge |
| 3 | SVG executes when inlined | Band 1, source and display modes; Xano; Magento (lane D) |
| 4 | CORS is not access control | Cloudflare edge |
| 5 | The edge sees plaintext | TLS; Cloudflare edge; TLS Full (strict) |
| 6 | Logs keep what they're sent | Xano; Shopify / Xano API (lane A); CRM · Xano (lane B) |
| 7 | SVG carries data, not just pixels | Band 1, source metadata and `<img>` display |
| 8 | The client is untrusted | Browser · Elm |
| 9 | Compiled is not hidden | Machine code definition |
| 10 | Hydration ships data into the page | Browser hydrates (lane A) |
| 11 | Shared caches mix customers | CDN · edge (lane A) |
| 12 | Server fetch runs before consent | Browser request; Next server (lane A) |
| 13 | `NEXT_PUBLIC_` compiles into the bundle | Next server (lane A) |
| 14 | TLS is hop by hop on a data bus | Cloudflare Worker (lane B) |
| 15 | Unverified or replayed webhooks | Shopify webhook back (lane B) |
| 16 | Queue rows outlive the message | Queue · webhook table (lane B) |
| 17 | Admin tokens at the edge | Cloudflare Worker (lane B) |
| 18 | Middleware sees everything | MuleSoft; SFCC (lane C) |
| 19 | The JVM has no in-process sandbox | Salesforce core; SFCC (lane C) |
| 20 | Consent isn't carried with the event | Google Merchant (lanes C and E); Shopify Customer Privacy API (lane E) |
| 21 | Retries duplicate writes | Google Merchant (lanes C and E); Azure (lane D); Cloudflare Worker (lane E) |
| 22 | Wasm host imports are the door | Shopify Function (lane E) |
| 23 | Containers share the kernel | Docker panel |
| 24 | Kubernetes Secrets are base64 | Kubernetes panel, etcd |
| 25 | Pod traffic is plaintext by default | Kubernetes panel, arrow between nodes |
| 26 | Secrets baked into images | Docker panel |
| 27 | The host can read VM memory | Virtual machine panel |
| 28 | The iPaaS keeps copies | Celigo (lane D) |
| 29 | Integration credentials are too broad | SAP S/4HANA (lane D) |
| 30 | Checkout JavaScript gets skimmed | Magento (lane D) |
| 31 | Batch files sit in plaintext | SAP S/4HANA (lane D) |

## The files

- **SVG:** [svg-base64-security-gaps.svg](/docs/svg-base64-security-gaps.svg), 1600 × 4290, with a `<title>` and `<desc>` for screen readers and search. Text uses Helvetica and Courier, and the labels avoid arrow characters so they display in any app.
- **JPG:** [svg-base64-security-gaps.jpg](/docs/svg-base64-security-gaps.jpg), carrying the same rights XMP and alt text as every image on this site (see [ALT, XMP and Favicons](/article/)).
- **Rights:** see the [rights page](/rights/).

When you reuse the SVG on another site, display it with `<img>` rather than inlining it. That is gap 3 applied to this diagram.

## Further reading

- [The Rust Programming Language](https://doc.rust-lang.org/book/) ("The Rust Book"):
  - [What is ownership?](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html), the rule behind the single-use `ConsentGrant`
  - [References and borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html), the `&` versus `&mut` permission split
  - [Unsafe Rust](https://doc.rust-lang.org/book/ch20-01-unsafe-rust.html), what "no `unsafe`" rules out
- [The Embedded Rust Book: `no_std`](https://docs.rust-embedded.org/book/intro/no-std.html), Rust on bare metal
- [Shopify: Rust for Functions](https://shopify.dev/docs/apps/build/functions/programming-languages/rust-for-functions), Rust compiled to Wasm
- [An Introduction to Elm](https://guide.elm-lang.org/) and [Elm ports](https://guide.elm-lang.org/interop/ports.html)
- [Machine Code/Rust/WASM, SVG/Native, Server/Client](/machine-code-rust-wasm/), the companion article with every fix
