#!/usr/bin/env bash
# Idempotent bring-up for the GCP Android-emulator dynamic-analysis box.
# Run ON the VM (android-avd) after provisioning with nested virt enabled.
# See README.md for provisioning + workstation tunnel commands.
set -euo pipefail

export ANDROID_SDK_ROOT="$HOME/android"
ADB="$ANDROID_SDK_ROOT/platform-tools/adb"
AVD_NAME="research"
SYS_IMG="system-images;android-34;google_apis;x86_64"
CAIDO_VER="v0.57.1"

echo "== 1. KVM + toolchain =="
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  openjdk-17-jdk-headless qemu-kvm cpu-checker unzip curl wget adb xz-utils \
  software-properties-common
sudo kvm-ok
sudo usermod -aG kvm "$USER" || true

echo "== 2. Android SDK + emulator + system image =="
if [ ! -x "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]; then
  mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
  wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdtools.zip
  unzip -q -o /tmp/cmdtools.zip -d "$ANDROID_SDK_ROOT/cmdline-tools"
  mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest" 2>/dev/null || true
fi
SDK="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin"
yes 2>/dev/null | "$SDK/sdkmanager" --sdk_root="$ANDROID_SDK_ROOT" --licenses >/dev/null 2>&1 || true
"$SDK/sdkmanager" --sdk_root="$ANDROID_SDK_ROOT" "platform-tools" "emulator" "$SYS_IMG"

echo "== 3. Create + launch AVD (headless, KVM, writable-system) =="
echo no | "$SDK/avdmanager" create avd -n "$AVD_NAME" -k "$SYS_IMG" -d pixel_5 --force
if ! pgrep -f qemu-system >/dev/null; then
  nohup "$ANDROID_SDK_ROOT/emulator/emulator" -avd "$AVD_NAME" \
    -no-window -no-audio -no-snapshot -no-boot-anim \
    -gpu swiftshader_indirect -accel on -writable-system \
    </dev/null >"$HOME/emulator.log" 2>&1 &
  disown
fi
"$ADB" wait-for-device
until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 3; done
"$ADB" root; sleep 3; "$ADB" wait-for-device
echo "AVD up: $("$ADB" shell getprop ro.product.cpu.abilist | tr -d '\r')"

echo "== 4. Frida (needs Python 3.11 — 22.04's 3.10 breaks frida-tools) =="
sudo add-apt-repository -y ppa:deadsnakes/ppa >/dev/null 2>&1
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.11 python3.11-venv >/dev/null 2>&1
[ -d "$HOME/frida-venv" ] || python3.11 -m venv "$HOME/frida-venv"
"$HOME/frida-venv/bin/pip" install -q --upgrade pip frida-tools
FV="$("$HOME/frida-venv/bin/frida" --version)"
wget -q "https://github.com/frida/frida/releases/download/${FV}/frida-server-${FV}-android-x86_64.xz" -O /tmp/fs.xz
unxz -f /tmp/fs.xz
"$ADB" shell "pkill -f frida-server" 2>/dev/null || true
"$ADB" push /tmp/fs /data/local/tmp/frida-server >/dev/null
"$ADB" shell chmod 755 /data/local/tmp/frida-server
"$ADB" shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"
sleep 4
"$HOME/frida-venv/bin/frida-ps" -U | head -5

echo "== 5. Caido headless (proxy :8080, UI :8081) =="
mkdir -p "$HOME/caido" && cd "$HOME/caido"
if [ ! -x ./caido-cli ]; then
  wget -q "https://storage.googleapis.com/caido-releases/${CAIDO_VER}/caido-cli-${CAIDO_VER}-linux-x86_64.tar.gz" -O caido.tgz
  tar xzf caido.tgz
fi
if ! pgrep -f caido-cli >/dev/null; then
  nohup ./caido-cli --proxy-listen 127.0.0.1:8080 --ui-listen 127.0.0.1:8081 --no-open \
    </dev/null >"$HOME/caido.log" 2>&1 &
  disown
  sleep 6
fi

echo "== 6. Point emulator at Caido =="
"$ADB" shell settings put global http_proxy 10.0.2.2:8080
echo "http_proxy = $("$ADB" shell settings get global http_proxy | tr -d '\r')"

echo
echo "DONE. Next: tunnel :8081 to your workstation, sign in to Caido, create a project."
echo "TLS interception: run a Frida SSL-unpinning script (primary). See RESEARCHER-GUIDE.md Appendix A."
