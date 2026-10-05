# game11ty Worker

Two Workers, tested in Cloudflare's runtime (workerd via Miniflare):

- `head.mjs` (SB-15): hardens every response's headers.
- `egress.mjs` (SB-23): the egress gate. Holds, classifies, evaluates and
  records every outbound payload; a refusal sends zero bytes. Diagnosis,
  record and refusal only: it never rewrites a payload.

## Test

    npm test            # 32 tests
    node mutate.mjs     # every rule must have a test that fails when it breaks

## Run the egress gate locally

Two terminals:

    npm run dev:stubs   # port 8790: stand-in ledger, claims check and fake vendor
    npm run dev         # port 8787: the gate, bound to the stand-ins

Then, in a third:

    npm run demo        # six payloads: allowed, PHI without a BAA, card in a note, ...

Or send your own:

    curl -s localhost:8787 -d '{"destination":"http://localhost:8790/vendor/model","region":"US",
      "actor":"agent:me","idempotency_key":"try-1","payload":{"reading":"38.9C"}}'
    curl -s localhost:8790/vendor     # bytes the fake vendor received
    curl -s localhost:8790/entries    # what the ledger recorded

`localhost:8790` plays a vendor with no BAA; `127.0.0.1:8790` plays one with a
BAA on file. Field tags and destinations are in `wrangler.jsonc` under
`POLICY`. An actor containing "revoked" fails the claims check.

`wrangler.jsonc` is wired for local development. Before any deploy, point
`LEDGER` and `CLAIMS` at the Xano system of record and the destinations at real
vendors; the stand-ins in `stubs/` are never deployed.
