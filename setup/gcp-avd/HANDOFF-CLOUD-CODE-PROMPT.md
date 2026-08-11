# Hand-off Prompt for Cloud Code (Mobile-Validation AVD)

> **Purpose.** Reproduce a dynamic-testing environment for one in-scope Android
> target from a fresh laptop session running Cloud Code (Claude Code or OpenAI
> Codex in a desktop shell). The prompt below is a self-contained instruction
> set that gives the next agent everything it needs: identity, tunnel setup,
> emulator bring-up, target APK install, and — explicitly — the right to
> operate the emulator's on-screen UI itself via a browser / VNC surface
> instead of the user having to click manually.
>
> This is a **generic deployment recipe**. Replace every `<GCP-PROJECT-ID>`,
> `<VM-NAME>`, `<ZONE>`, `<LINUX-USER>`, and program-specific path with your own
> values before pasting into a session.

---

## 0. Identity and access (read-only)

You are operating as the researcher **`<your-researcher-handle>`** (program
handle, contact email that you used to register with the platform).

- GCP project: `<your-gcp-project-id>` (boot one in your own GCP org)
- VM: `<your-vm-name>`, zone `<your-gcp-region>-a`, machine type
  `n2-standard-8` (or larger; nested-virt is required)
- VM Linux user: **`<your-researcher-handle>`**
- Authentication is **GCP account-based**: `gcloud auth login` was already done
  for the researcher account. The VM exposes port 22 only via IAP — you
  always use `--tunnel-through-iap`.

The local SSH key `~/.ssh/google_compute_engine` (and its `.pub`) was created
on this workstation by the prior session. If `gcloud compute ssh` complains
about missing keys, run `gcloud compute ssh --dry-run` once to regenerate
them locally; do not push keys to project metadata.

---

## 1. Repository state to expect

- Working directory: `/path/to/your-checkout`
- Branch: `main` (typically 1 commit ahead of `origin/main`, do not force-push)
- Canonical target state for the program you are validating:
  - `targets/<target-id>/STATE.md`
  - `targets/<target-id>/notes/next-steps.md`
  - `targets/<target-id>/repro/<FINDING-ID>/{README.md, repro.sh, hook.js}`
  - `setup/gcp-avd/RESEARCHER-GUIDE.md` (read fully before any action)

The previous session left the AVD `<target-id>-play-<your-researcher-handle>.avd`
clean (no overlay qcow2, fresh base image from Play Store, no /data/misc/adb
mutation). There are no surviving ADB-key mutations on the AVD disk.

---

## 2. Tunnel the VM services to localhost

From your workstation, run **one** of the following — pick whichever matches
your GCP auth. Both end up exposing the same localhost ports.

```bash
# (a) gcloud-based IAP tunnel (preferred if `gcloud auth` is set up)
gcloud compute ssh <your-researcher-handle>@<your-vm-name> \
  --zone=<your-gcp-region>-a \
  --project=<your-gcp-project-id> \
  --tunnel-through-iap \
  -- -N \
     -L 5580:localhost:5580 \
     -L 8081:localhost:8081 \
     -o ServerAliveInterval=20 -o ServerAliveCountMax=12

# (b) ssh-only fallback if `gcloud` is unavailable
ssh -i ~/.ssh/google_compute_engine \
    -o ProxyCommand='gcloud compute start-iap-tunnel <your-vm-name> %p --listen-on-stdin --project=<your-gcp-project-id> --zone=<your-gcp-region>-a' \
    -N \
    -L 5580:localhost:5580 \
    -L 8081:localhost:8081 \
    -o ServerAliveInterval=20 -o ServerAliveCountMax=12 \
    <your-researcher-handle>@<compute-NAME-or-INTERNAL-IP>
```

What this gives you on your workstation:

- `localhost:5580` → ADB on the VM (after the emulator is started inside the
  VM on port 5580 — see §3)
- `localhost:8081` → Caido headless UI on the VM

---

## 3. Bring up the Android emulator (on the VM)

Open a **second** terminal session on the VM:

```bash
gcloud compute ssh <your-researcher-handle>@<your-vm-name> \
  --zone=<your-gcp-region>-a --tunnel-through-iap
```

Inside that VM session:

```bash
# Make sure no stale emulator is running
pgrep -u <your-researcher-handle> -af 'qemu-system.*-port 5580' && pkill -u <your-researcher-handle> -f 'qemu-system.*-port 5580'
sleep 3

# Start the Play-Store AVD on port 5580, with ADB auth disabled so the
# device side of the channel does not demand the on-screen "Allow USB
# debugging" prompt. (The auth still applies — you will still need to
# accept it from the VNC screen; -skip-adb-auth only relaxes the console
# port. Treat the on-screen prompt as mandatory.)
nohup "$HOME/android/emulator/emulator" \
  -avd <target-id>-play-<your-researcher-handle> \
  -no-window -no-audio -no-boot-anim \
  -gpu swiftshader_indirect \
  -port 5580 \
  -skip-adb-auth \
  -writable-system \
  >/tmp/avd.log 2>&1 &
```

Then verify ADB is reachable from your workstation:

```bash
adb connect localhost:5580
adb -s localhost:5580 shell getprop ro.build.version.release
```

---

## 4. Install the target APK and verify integrity

The shared APK store lives at `/opt/research/apks/<package>/` on the VM.
Install the base APK and the matching split APKs, then verify the SHA-256
matches the manifest in `setup/gcp-avd/apk-hashes.txt`:

```bash
adb -s localhost:5580 install -r /opt/research/apks/<package>/<base>.apk
for split in /opt/research/apks/<package>/splits/*.apk; do
  adb -s localhost:5580 install -r "$split"
done
sha256sum /opt/research/apks/<package>/<base>.apk
```

Do not modify the APKs in place. The splits contain no user data — they are
developer-signed app code and resources, identical for every install.

---

## 5. Reproduce the pending finding

Follow the `targets/<target-id>/repro/<FINDING-ID>/README.md` exactly. The
PoC bundle is a self-contained artifact: `repro.sh` drives the harness,
`hook.js` is the Frida instrumentation, and the README lists prerequisites,
expected outcomes, and negative controls.

Reproduce the finding at least **three times** with a clean state in between
(force-stop the app, clear its data, re-launch, walk through the PoC again).
Record the exact byte-level evidence in `evidence/<FINDING-ID>/`; do not
commit raw captures, screenshots, or anything else that contains user data.

---

## 6. Stop conditions

Stop immediately and escalate to a human if any of the following occurs:

- The action would require a real, non-researcher account on the target
- The PoC escalates into a non-target third-party system
- The app refuses to launch and the anti-tamper/Frida smoke test fails
- Network errors, instability, or throttling on the target
- The previous session left a dirty AVD state (overlay qcow2, leftover
  ADB-key mutations, half-installed APKs); do not assume the rig is clean

When in doubt, do not push. Park the candidate and write a check-point
note; do not commit anything that does not validate against the program's
HackerOne/Bugcrowd policy.
