# Security Research Policy

This policy applies to every human, agent, script, and tool operating from this repository. It is a mandatory gate, not a substitute for a target program's current rules.

## Authorization and scope precedence

Test only assets and techniques explicitly authorized by the target's current published program policy and the target `contract.yaml`. The live program policy takes precedence over repository notes whenever it is newer or stricter. If scope, ownership, authorization, or policy interpretation is uncertain, stop testing until a human confirms it. Do not treat public reachability as permission.

## Request rates and automation

Obey the program's stated limits. Where it is silent, default to no more than 1–2 aggregate requests per second, wait at least one second between API calls, avoid concurrency, and stop on throttling or instability. Include every required researcher-identification header. Automation must have bounded requests, timeouts, logging, and a working kill switch.

## Accounts and identities

Use only researcher-owned accounts, test tenants, devices, payment instruments, and data, unless the program explicitly supplies or authorizes another resource. Never access, modify, impersonate, or attempt to retain another person's account or session. Do not solicit credentials or involve unsuspecting users.

## Data minimization and handling

Collect the minimum evidence needed to prove the authorized claim. Stop reading when non-researcher data appears. Do not download bulk records. Redact tokens, cookies, personal data, secrets, internal identifiers, and private keys from committed artifacts. Keep raw captures, device backups, APKs, Burp profiles, ngrok tokens, and private CA material outside Git in protected local storage with the shortest practical retention period.

## Third-party systems

Do not pivot into infrastructure, cloud metadata, SaaS tenants, webhooks, email/SMS recipients, package registries, or other systems not explicitly in scope, even if an in-scope asset can reach them. Use researcher-controlled callback endpoints and inert test data. Treat every redirect or integration boundary as a new authorization boundary.

## Availability and prohibited testing

Denial-of-service, stress, load, resource-exhaustion, destructive, persistence, and social-engineering tests are prohibited unless the program gives explicit written authorization for the exact test. Never delete or corrupt data, degrade service, flood queues, lock accounts, or interfere with other users. Prefer a minimal non-destructive proof and negative controls.

## Cleanup

After testing, revoke temporary tokens and callback URLs; remove test accounts, webhooks, files, packages, tunnels, proxy rules, certificates, hooks, and device instrumentation when safe; restore modified settings; and document any artifact that cannot be removed. Retain only sanitized evidence required for review and disclosure.

## Emergency stop conditions

Stop immediately if any of the following occurs:

- the asset or technique appears out of scope or authorization cannot be confirmed;
- another user's data, account, credential, secret, or private communication becomes accessible;
- service errors, latency, throttling, resource pressure, or instability increase;
- a test causes an unintended write, privilege change, outbound action, financial effect, or third-party interaction;
- a kill switch, logging, rate limiter, or containment control fails;
- the program, asset owner, or platform asks testing to stop.

Preserve minimal logs, disable automation/tunnels, avoid further interaction, notify the program through its designated channel when appropriate, and wait for explicit direction before resuming.
