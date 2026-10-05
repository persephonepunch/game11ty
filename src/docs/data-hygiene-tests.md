# Data hygiene test requirements

Each requirement is written Given / When / Then so it can become an automated test. **Level** says where it runs: *unit* (pure function), *integration* (real database or API in a test workspace), *canary* (a planted marker value searched for afterwards), *CI* (a static check that fails the build).

Use clearly fake marker values: card `4242 4242 4242 4242`, email `canary+dh@example.com`, name `Zz Canary`.

| ID | Requirement | Given | When | Then | Level |
| --- | --- | --- | --- | --- | --- |
| DH-01 | Every field is classified | The schema export and the field-class registry | CI compares them | The build fails on any field with no `data_class` | CI |
| DH-02 | No card data in systems you control | The canary card number is entered at checkout | The order completes and logs flush | The card number appears in no database, log, Worker trace, cache or prompt; only the provider's token is stored | canary |
| DH-03 | PHI goes only to BAA vendors | A payload tagged `phi` | It is routed to a vendor or model without a BAA on file | The call is refused before any bytes leave, and the refusal is recorded | integration |
| DH-04 | One system of record per fact | The SoR map and a copy system (e.g. Shopify tags) | The copy tries to write a SoR-owned fact (e.g. an entitlement) | The write is rejected; the SoR is unchanged | integration |
| DH-05 | Models receive minimised data | An agent task that needs "is ink low?" | The prompt sent to the model is captured | It contains IDs and derived facts only; no email, phone, address or canary name | canary |
| DH-06 | Vector stores hold pseudonymous IDs | A record containing the canary name and email is embedded | The vector store's metadata and source text are searched | Neither canary value is present; only the pseudonymous ID | canary |
| DH-07 | No PII in URLs, logs or token extras | A request made with the canary email | Access logs, error logs and a decoded token are searched | The canary email appears in none of them | canary |
| DH-08 | Timestamps are ISO 8601 UTC, with source and record times | Records written by each integration | `occurred_at` and `recorded_at` are validated | Both exist, match `YYYY-MM-DDTHH:MM:SS(.sss)Z`; a local offset or an epoch number is rejected on write | unit |
| DH-09 | ISO codes on write | A write with region `UK`, currency `pounds`, language `English` | The write is submitted | It is rejected; `GB`, `GBP`, `en-GB` are accepted | unit |
| DH-10 | Ledger is append-only | An existing ledger entry | An UPDATE or DELETE is attempted with application credentials | It is refused; a correction is accepted only as a new entry with `reverses` set | integration |
| DH-11 | Ledger entries are attributable | Any action by an agent | The ledger entry is read | `actor`, `on_behalf_of`, `claim_id`, `data_class` and `source` are all non-null | integration |
| DH-12 | Repeat with the same key does nothing | An action submitted with key K and result R | The same request with K is sent again | No second action; the response is R; one ledger row for K | integration |
| DH-13 | Concurrent duplicates produce one action | 20 identical requests with key K | They are sent in parallel | Exactly one action and one ledger row; 19 responses return the stored result | integration |
| DH-14 | Key survives into the ERP | A batch to SAP containing key K as the external reference | The same batch is replayed | The ERP creates no duplicate document | integration |
| DH-15 | Stale data is refused or escalated | Stock data with `recorded_at` older than the action's tolerance | An agent attempts the last-unit sale | The action is refused or sent to a human; nothing is sold | unit |
| DH-16 | Batch copies never grant | An entitlement present only in the 15-minute ERP copy, absent in the SoR | An agent requests the entitled action | It is refused | integration |
| DH-17 | Revocation is immediate | A valid token issued before consent is withdrawn | The agent acts one second after the withdrawal entry | The action is refused; the refusal is recorded | integration |
| DH-18 | Labels never grant | A token whose extras claim a role, or a glTF/tag value claiming a SKU right | The protected action is requested with no matching SoR claim | It is refused | integration |
| DH-19 | Routing and keys stay server-side | Requests tagged by data class and region | Model calls are inspected | Each goes to the provider allowed for that class and region; no API key appears in the client bundle or the prompt | integration + CI |
| DH-20 | Reconcile, don't overwrite | A batch record whose `occurred_at` is older than the ledger's latest entry for that fact | Reconciliation runs | The record is not applied; a review item lists source, both values and both timestamps | integration |

## Definition of done

- Every DH test that applies to the change passes, and n/a items have a one-line reason.
- Canary tests run in a test workspace, never against production customer data.
- Failures block release in this order: DH-02, DH-03 (regulated data), then DH-16 to DH-18 (permissions), then DH-12 to DH-14 (idempotency), then the rest.
