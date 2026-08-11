# Researcher Guide — Cloud AVD Dynamic-Testing Environment

Onboarding for a researcher testing in-scope Android apps on a shared GCP
Android-emulator rig. Read this fully before touching a target. It does **not**
override your project's `SECURITY-RESEARCH-POLICY.md`, `CLAUDE.md`, or each
program's HackerOne / Bugcrowd policy — those win.

This is a **generic deployment recipe**. Replace every `<GCP-PROJECT-ID>`,
`<VM-NAME>`, `<ZONE>`, `<LINUX-USER>`, and program-specific path with your own
values before pasting into a session.

## 1. What the environment is

- **VM:** `<your-vm-name>` (GCP project `<your-gcp-project-id>`, zone
  `<your-gcp-region>-a`, `n2-standard-8`, nested-virt on).
- **Emulator:** official Android SDK AVD, **Android 14** (`google_apis` x86_64),
  **rooted** (`adb root`), `abilist = x86_64,arm64-v8a` so ARM-only APKs run
  under translation. Headless under KVM, launched with `-writable-system`.
- **Tooling (shared services, run by the operator account):**
  - **Frida** server on the emulator; `frida-tools` in
    `~<your-researcher-handle>/frida-venv`.
  - **Caido** headless: proxy `127.0.0.1:8080`, UI `127.0.0.1:8081`.
  - Emulator system proxy is set to `10.0.2.2:8080` → Caido.
- **APKs:** shared, read/write for both accounts, in
  **`/opt/research/apks/<package>/`** (device-extracted; see the hash
  manifest in section 6).

You mostly **use** the running emulator (adb, Frida, Caido over localhost).
To restart a shared service or manage the SDK you have `sudo`.

## 2. Access (secure, identity-gated)

> **CRITICAL — keep two separate GCP projects, do not mix.** This rig is
> **only for Android/mobile dynamic testing.** Non-mobile compute
> (source-reproduction, `go test`, web/API harnesses, cyber-range labs) does
> **NOT** belong on this box and must **NOT** use this project's credentials.

| Purpose | GCP project | Access path | Identity |
|---|---|---|---|
| **Android/mobile dynamic testing only** (this rig, `<your-vm-name>`) | `<your-gcp-project-id>` | `gcloud compute ssh <your-researcher-handle>@<your-vm-name> --tunnel-through-iap` — authenticated via the operator's own gcloud CLI; no on-disk SSH key required. | Operator's authenticated `gcloud` CLI account |
| **Non-mobile compute / cyber-range / source-repro** (e.g. `go test`, `bbr` labs) | `<your-lab-name>` | OS Login over IAP, e.g. `<your-bastion-name>` | Operator's authenticated `gcloud` CLI account |

The `<your-vm-name>` instance has `enable-oslogin: FALSE` and a metadata
`ssh-keys` entry historically registered for a separate collaborator account.
That entry is a legacy artifact and **is not the access path for the
operator's session.** The operator accesses the box via the authenticated
`gcloud` CLI, which uses IAP tunneling plus the operator's Google-account
credentials to mint a session on the VM. No SSH key lives on disk. Never
edit the metadata `ssh-keys` entry; it does not gate the operator's access,
and rewriting it can lock out the legacy collaborator.

## 2. Access (authenticated `gcloud` CLI; no SSH key on disk)

Use only the operator's authenticated `gcloud` CLI to reach the box. The CLI
handles IAP tunneling and authenticates the session via the operator's
Google-account credentials — no on-disk SSH key is needed.

```bash
gcloud compute ssh <your-researcher-handle>@<your-vm-name> --zone=<your-gcp-region>-a --tunnel-through-iap
```

For port-forwarding (adb to emulator, Caido UI):

```bash
gcloud compute ssh <your-researcher-handle>@<your-vm-name> --zone=<your-gcp-region>-a --tunnel-through-iap \
  -- -L 5555:localhost:5555 -L 8081:localhost:8081
```

- `localhost:5555` → adb to the emulator (`adb connect localhost:5555`).
- `localhost:8081` → Caido UI in your browser.

**Always use `--tunnel-through-iap`.** Direct `gcloud compute ssh` to the VM's
external IP gets **rate-limited/throttled** under repeated connections
(symptom: intermittent then sustained `exit code 255`). IAP routes through
Google's proxy and stays reliable, and it's how access is gated anyway. For
long commands, add `-- -o ServerAliveInterval=20 -o ServerAliveCountMax=12`
so the session isn't reset mid-wait.

For any authenticated flow, start an isolated Caido instance/project on
separate ports (`--proxy-listen 127.0.0.1:8090 --ui-listen 127.0.0.1:8091`) and
point the isolated emulator at `10.0.2.2:8090`. Never put account credentials,
tokens, cookies, or personal data in the shared project. Use the shared capture
only for a flow known not to carry account secrets; when uncertain, isolate it.

## 3. Testing workflow (per target)

1. **Install the APK.** Modern apps ship as **split App Bundles**, so a single
   device-extracted APK is only the **base** and `adb install` fails with
   `INSTALL_FAILED_MISSING_SPLIT`. Get the full split set from a device that
   has the app installed and `install-multiple`:

   ```bash
   # on a phone with the app: list base + config splits
   adb -s <phone> shell pm path <package>          # base.apk + split_config.{abi,dpi,locale}.apk
   adb -s <phone> pull <each path>                 # then scp the splits to the VM
   # on the emulator:
   adb install-multiple -r -g base.apk split_config.arm64_v8a.apk split_config.<dpi>.apk split_config.<locale>.apk
   ```

   The emulator's `abilist` includes `arm64-v8a` (translation), so the phone's
   `arm64_v8a` split installs fine — no separate x86 split needed.

   **Pre-staged:** complete split sets for your current targets belong on the
   VM at **`/opt/research/apks/<package>/`**. Install any of them with:

   ```bash
   adb install-multiple -r -g /opt/research/apks/<package>/*.apk
   ```

2. **Anti-tamper smoke test — the real go/no-go.** Launch the app; confirm it
   runs on the rooted emulator and that `frida-ps -U` sees its process and
   Frida can attach. If the app hard-blocks the emulator/root/Frida, **stop**
   and record the blocker. With a proxy set but no trusted CA/unpinning, some
   apps will land on a `CertFailActivity` — that's a TLS artifact of the
   proxy, not anti-tamper; clear the proxy or run SSL-unpinning. Aggressive
   anti-cheat apps (kernel-level, attestation-based) are still expected-hard;
   retail/travel apps are usually lighter.

3. **TLS interception.** Primary = a **Frida universal SSL-unpinning** script
   (defeats validation *and* pinning). Secondary = Caido CA in the
   Android-14 Conscrypt-APEX store. Full concrete steps are inlined in
   **Appendix A** below.

4. **Capture through Caido**, drive the target flow, and record evidence.

5. **Evidence:** minimum needed to prove the authorized claim, **redacted** —
   no PII, tokens, cookies, device IDs, or third-party data. Keep raw
   captures/APKs out of Git.

## 4. Rules of engagement (hard)

- Stay inside each program's **scope, safe-harbor, rate limits, and required
  identification** (see section 6). Test only researcher-owned accounts and
  content.
- **General integrity rule (matches most programs):** vulnerabilities that
  require root/jailbreak of *another user's* device are out of scope. Your
  emulator being rooted is fine (it's your test rig) — the *finding* must
  not depend on victim-device root.
- **Header / alias requirement (matches most programs):** register test
  accounts with your platform alias, or include the required research header
  where an email alias can't be used.
- No destructive actions, no bulk data pull, no touching other users' data.
  Stop reading the moment non-researcher data appears.
- A finding is not report-ready until it clears the target's qualification
  gates in its `findings-manifest.json` (current exact APK + version/hash,
  isolated account, redacted entry + authoritative-result evidence, a
  negative control isolating the claimed security control, and non-self
  impact beyond app navigation).

## 5. What to work on

Priority is **demonstrable, in-scope security impact**, not coverage. Pick
findings whose exact APK, current policy, isolated account, isolated capture,
and ADB/Frida readiness gates are stable. Otherwise choose a fresher target
with a same-codebase trigger and impact. Coordinate ownership to avoid
collision.

## 6. In-scope targets on this rig (verified at bring-up)

APKs staged in `/opt/research/apks/`. Confirm the current package still matches
the program's in-scope asset before reporting; re-read the live HackerOne /
Bugcrowd policy first.

| App | In-scope package | Bounty (H/Crit) | Notes |
|-----|------------------|------------------|-------|
| `<app-1>` | `<com.example.app1>` | `<amount>` | `<short notes>` |
| `<app-2>` | `<com.example.app2>` | `<amount>` | `<short notes>` |

Region-locked apps (US-only, SEA-only, etc.) are **not** on this rig unless
explicitly bridged via VPN.

APK SHA-256 provenance is recorded per file; verify with
`sha256sum /opt/research/apks/<package>.apk` before use.

## 7. Cost & housekeeping

The VM bills ~$0.38/h while running. The last researcher off must stop
`<your-vm-name>` unless an explicit, time-bounded handoff names the next
operator. Record the final GCP status in the session ledger. Emulator,
Frida, and Caido processes do not survive a VM stop; relaunch mirrors
[`bringup.sh`](./bringup.sh). Stopped persistent disks can still incur
storage charges.

## Appendix A — TLS interception (Frida SSL-unpinning + Caido CA)

All commands run on the VM against the emulator (`adb`), which already has
`adb root`. Caido's proxy is `127.0.0.1:8080` on the VM; the emulator reaches
it at `10.0.2.2:8080`.

**A.0 — Primary: Frida universal SSL-unpinning (defeats validation AND
pinning).** The reliable path on Android 14. Run a universal unpinning script
against the target so its TLS trusts Caido's CA and pinning is bypassed at
runtime:

```bash
frida -U -f <package> -l ~/frida-scripts/frida-ssl-unpinning.js
```

Well-known scripts: HTTPToolkit's "android-ssl-unpinning" or the
"frida-multiple-unpinning" gist (stage a sanitized copy under
`~/frida-scripts/`; do not commit target data). With unpinning active you
only need traffic routed to Caido (A.3); the system-CA install (A.1–A.2) is
optional and only helps non-pinned apps.

**A.1 — Export Caido's CA + compute the Android store filename.**
In Caido: Settings → export the CA certificate as `caido-ca.pem`/`caido-ca.der`.

```bash
openssl x509 -in caido-ca.pem -outform DER -out caido-ca.der   # if you exported PEM
HASH=$(openssl x509 -inform DER -in caido-ca.der -noout -subject_hash_old | head -c 8)
cp caido-ca.der "${HASH}.0"          # Android's legacy subject_hash_old name (not a SHA-256)
adb push "${HASH}.0" /sdcard/${HASH}.0
```

```
adb shell su 0 cp /sdcard/${HASH}.0 /apex/com.android.conscrypt/cacerts/
adb shell su 0 chmod 644 /apex/com.android.conscrypt/cacerts/${HASH}.0
```

**A.3 — Route emulator traffic to Caido.**

```bash
adb shell settings put global http_proxy 10.0.2.2:8080
```

Reset to none when done:

```bash
adb shell settings put global http_proxy :0
```

**A.4 — Verify.** In Caido, open a target flow you expect to make an HTTPS
call. If nothing shows up, check the Android system proxy and the
unpinning script's status. Re-pin when the capture is done.
