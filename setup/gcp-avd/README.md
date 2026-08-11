# GCP Android Emulator (AVD) — cloud dynamic-analysis environment

Generic deployment guide for a researcher-isolated Android dynamic-testing
environment. Replace every `<GCP-PROJECT-ID>`, `<VM-NAME>`, `<ZONE>`, and
program-specific path with your own values before pasting into a session.

The setup runs the **official Android SDK emulator** on a GCP x86 VM with
**nested virtualization + KVM**, giving a rooted Android 14 image with
`arm64-v8a` translation for ARM-only target APKs. Tooling: **Frida** +
**Caido** (headless).

This is a single mobile dynamic-PoC process — no hardware needed. The
recipe is intentionally generic; concrete APKs and program-specific paths
are filled in by the operator at bring-up.

## Why this and not a redroid Docker path

redroid borrows the **host** kernel's binder. Modern GCP kernels expose
binder only via **binderfs**, but redroid's Android (all versions 13–16)
expects legacy static `/dev/binder` nodes that its `ueventd` materialises —
and wipes `/dev` on boot, so injected nodes don't survive. The bridge module
(`redroid-modules`) no longer compiles on 5.15+ (API drift: `mmap_sem` →
`mmap_lock`, `simple_rename`, security-hook sigs). It is a genuine dead end
on cloud kernels. The AVD emulator ships **its own guest kernel**, so it
has no host-binder dependency — it just works.

## Provision (from your workstation)

```bash
gcloud compute instances create <your-vm-name> \
  --zone=<your-gcp-region>-a \
  --machine-type=n2-standard-8 \
  --enable-nested-virtualization \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=64GB --boot-disk-type=pd-ssd
```

Then SSH in and run `bringup.sh` (idempotent). It installs KVM + JDK, the
Android SDK/emulator, a `google_apis` x86_64 API-34 image (root-capable),
creates+launches a headless AVD, installs Frida (needs **Python 3.11** —
22.04's 3.10 breaks current `frida-tools`), and Caido CLI headless.

## Access from your workstation (two SSH tunnels)

> **Scope note:** these tunnels are for **Android/mobile dynamic testing on
> this rig only.** Non-mobile compute (source-reproduction, `go test`,
> web/API harnesses, cyber-range labs) belongs in a separate project
> (`<your-lab-name>`, OS Login over IAP), not here. See
> `RESEARCHER-GUIDE.md` §2 "two separate GCP projects".

```bash
# adb to the emulator
gcloud compute ssh <your-vm-name> --zone=<your-gcp-region>-a -- -N -L 5555:localhost:5555 &
adb connect localhost:5555        # then: adb root

# Caido web UI
gcloud compute ssh <your-vm-name> --zone=<your-gcp-region>-a -- -N -L 8081:localhost:8081 &
# open http://localhost:8081 , sign in to Caido (free account), create a project
```

## Interception (Caido)

- In-emulator proxy is already set to `10.0.2.2:8080` (VM loopback = Caido
  proxy). Clear with `adb shell settings put global http_proxy :0`.
- **Caido needs a signed-in project before the proxy forwards** (a fresh
  proxy request returns HTTP 500 until then). Log in via the UI tunnel first.
- **TLS: primary = Frida universal SSL-unpinning** (defeats validation +
  pinning). Secondary = install Caido's CA into the Android-14
  Conscrypt-APEX store — see [`RESEARCHER-GUIDE.md`](./RESEARCHER-GUIDE.md)
  Appendix A for both.

## Conserve credit

`n2-standard-8` ≈ $0.38/h running. `gcloud compute instances stop <your-vm-name>`
when idle (disk-only billing while stopped); snapshot the disk to rebuild
fast.

## Optional: Caido MCP

The community `c0tton-fluff/caido-mcp-server` exposes Caido traffic to
Claude Code over MCP — it lets the assistant browse/replay captured HTTP
during a hunt. Wire-up is an operator decision.
