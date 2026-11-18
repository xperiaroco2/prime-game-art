#!/usr/bin/env bash
# Sets up the art pipeline's tools in a Claude Code cloud container (Ubuntu 24.04, x86_64; art #136). Downloads the
# pinned Blender, glTF-Validator and Godot (tools/runner/pins.py) for Linux from their official sources, checks each
# download, unpacks it outside the repo, pulls the Git LFS files, makes the raw root, and prints the environment lines
# to export. With --window it also installs Xvfb and Mesa (llvmpipe, lavapipe) from apt for Godot's off-screen window
# runs under xvfb-run. Safe to run again: a tool already unpacked is kept.
#
#   bash tools/cloud/setup.sh [--window] [--no-lfs]      # then: eval "$(bash tools/cloud/setup.sh --env)"
#
# ART_TOOLS_DIR (default /opt/art-tools) holds the tools; ART_RAW_DIR (default prime-art-raw beside the checkout) the
# raw root. The checksums: Blender's from the official blender-<v>.sha256, Godot's from the release's SHA512-SUMS.txt;
# the Khronos validator publishes none, so its hash is the one measured on 2026-11-18 (like pins.py's Windows zip).
set -euo pipefail

BLENDER=5.2.2
BLENDER_SERIES=5.2
GLTF_VALIDATOR=2.0.0-dev.3.10
GLTF_VALIDATOR_SHA256=168eba887964125abe17ae97899b38d0b3cfd73c266c78424c194929ddcbc522
GODOT=4.7.2

repo="$(cd "$(dirname "$0")/../.." && pwd)"
tools="${ART_TOOLS_DIR:-/opt/art-tools}"
raw="${ART_RAW_DIR:-$(dirname "$repo")/prime-art-raw}"
blender_bin="$tools/blender/blender-$BLENDER-linux-x64/blender"
validator_bin="$tools/gltf-validator/$GLTF_VALIDATOR/gltf_validator"
godot_bin="$tools/godot/$GODOT/Godot_v$GODOT-stable_linux.x86_64"

env_lines() {
  echo "export BLENDER_BIN=$blender_bin"
  echo "export GLTF_VALIDATOR_BIN=$validator_bin"
  echo "export GODOT_BIN=$godot_bin"
  echo "export ART_RAW_DIR=$raw"
  echo "export PYTHON_BIN=python3"
}

window=0
lfs=1
for arg in "$@"; do
  case "$arg" in
    --env) env_lines; exit 0 ;;
    --window) window=1 ;;
    --no-lfs) lfs=0 ;;
    *) echo "setup.sh: unknown argument $arg (--window, --no-lfs, --env)" >&2; exit 2 ;;
  esac
done

for pin in "BLENDER = \"$BLENDER\"" "GLTF_VALIDATOR = \"$GLTF_VALIDATOR\"" "GODOT = \"$GODOT\""; do
  grep -qF "$pin" "$repo/tools/runner/pins.py" || { echo "setup.sh: pins.py no longer has $pin; update this script" >&2; exit 1; }
done

# Each download goes into its own new folder under a fresh temporary directory, never into the repo.
dl="$(mktemp -d)"
trap 'rm -rf "$dl"' EXIT
fetch() { curl -fsSL --retry 3 -o "$1" "$2"; }

if [ ! -x "$blender_bin" ]; then
  echo "Blender $BLENDER: downloading"
  mkdir -p "$dl/blender" "$tools/blender"
  base="https://download.blender.org/release/Blender$BLENDER_SERIES"
  fetch "$dl/blender/blender-$BLENDER.sha256" "$base/blender-$BLENDER.sha256"
  fetch "$dl/blender/blender-$BLENDER-linux-x64.tar.xz" "$base/blender-$BLENDER-linux-x64.tar.xz"
  (cd "$dl/blender" && grep " blender-$BLENDER-linux-x64.tar.xz\$" "blender-$BLENDER.sha256" | sha256sum -c -)
  tar -xJf "$dl/blender/blender-$BLENDER-linux-x64.tar.xz" -C "$tools/blender"
  rm -rf "$dl/blender"
fi

if [ ! -x "$validator_bin" ]; then
  echo "glTF-Validator $GLTF_VALIDATOR: downloading"
  mkdir -p "$dl/gltf" "$tools/gltf-validator/$GLTF_VALIDATOR"
  name="gltf_validator-$GLTF_VALIDATOR-linux64.tar.xz"
  fetch "$dl/gltf/$name" "https://github.com/KhronosGroup/glTF-Validator/releases/download/$GLTF_VALIDATOR/$name"
  echo "$GLTF_VALIDATOR_SHA256  $dl/gltf/$name" | sha256sum -c -
  tar -xJf "$dl/gltf/$name" -C "$tools/gltf-validator/$GLTF_VALIDATOR"
fi

if [ ! -x "$godot_bin" ]; then
  echo "Godot $GODOT: downloading"
  mkdir -p "$dl/godot" "$tools/godot/$GODOT"
  name="Godot_v$GODOT-stable_linux.x86_64.zip"
  base="https://github.com/godotengine/godot/releases/download/$GODOT-stable"
  fetch "$dl/godot/SHA512-SUMS.txt" "$base/SHA512-SUMS.txt"
  fetch "$dl/godot/$name" "$base/$name"
  (cd "$dl/godot" && grep "  $name\$" SHA512-SUMS.txt | sha512sum -c -)
  python3 -I -m zipfile -e "$dl/godot/$name" "$tools/godot/$GODOT"
  chmod +x "$godot_bin"
fi

if [ "$window" = 1 ]; then
  echo "apt: xvfb, xauth, mesa-vulkan-drivers, libgl1-mesa-dri"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq xvfb xauth mesa-vulkan-drivers libgl1-mesa-dri >/dev/null
fi

if [ "$lfs" = 1 ]; then
  echo "git lfs pull"
  git -C "$repo" lfs pull
fi
mkdir -p "$raw"

first() { printf '%s\n' "${1%%$'\n'*}"; }  # the first line (no `| head`: with pipefail its SIGPIPE fails the script)
first "$("$blender_bin" -b --version 2>/dev/null)"
first "$("$validator_bin" --version 2>&1)"
echo "Godot $("$godot_bin" --headless --version 2>/dev/null)"
echo
echo "# Export these, then run: bash tools/run.sh doctor"
env_lines
