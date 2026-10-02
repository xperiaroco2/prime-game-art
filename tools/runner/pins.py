"""Pinned tool versions and their default install paths: one place for every command.

The engineer approved the downloads in chat on 2026-10-02 (xperiaroco2/prime-game#165). Installs live outside every
repository; an environment variable overrides each default path.
"""

from __future__ import annotations

PYTHON_MIN = (3, 11)

# Blender LTS, the portable Windows zip from download.blender.org; SHA-256 from the official blender-5.2.2.sha256.
BLENDER = "5.2.2"
BLENDER_ZIP = "blender-5.2.2-windows-x64.zip"
BLENDER_ZIP_SHA256 = "3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535"
BLENDER_URL = f"https://download.blender.org/release/Blender5.2/{BLENDER_ZIP}"
BLENDER_ENV = "BLENDER_BIN"
BLENDER_DEFAULT = "D:/tools/blender/5.2.2/blender.exe"

# Khronos glTF-Validator; the project publishes no checksum, so this is the hash of the zip we downloaded.
GLTF_VALIDATOR = "2.0.0-dev.3.10"
GLTF_VALIDATOR_ZIP = f"gltf_validator-{GLTF_VALIDATOR}-win64.zip"
GLTF_VALIDATOR_ZIP_SHA256 = "c5068f51205deedc28acc3529ee7e11ee60e853454f673093398eba80142202c"
GLTF_VALIDATOR_URL = f"https://github.com/KhronosGroup/glTF-Validator/releases/download/{GLTF_VALIDATOR}/{GLTF_VALIDATOR_ZIP}"
GLTF_VALIDATOR_ENV = "GLTF_VALIDATOR_BIN"
GLTF_VALIDATOR_DEFAULT = f"D:/tools/gltf-validator/{GLTF_VALIDATOR}/gltf_validator.exe"

# The game's pinned Godot (xperiaroco2/prime-game, tools/runner/pins.py); the console exe, from GODOT_BIN.
GODOT = "4.7.2"
GODOT_VERSION_PREFIX = "4.7.2.stable.official"
GODOT_ENV = "GODOT_BIN"

# Raw generations and downloads: outside every repository, never in git (the engineer's choice, 2026-10-02).
RAW_ENV = "ART_RAW_DIR"
RAW_DEFAULT = "D:/prime-art-raw"
# Chosen originals are copied here as a backup; %OneDrive% is the engineer's OneDrive folder.
RAW_BACKUP_ENV = "ART_RAW_BACKUP_DIR"
RAW_BACKUP_SUBDIR = "prime-art-raw"

# Meshy: the API key comes from this variable (the process environment, else the Windows user environment). It is
# never printed, logged or committed.
MESHY_KEY_ENV = "MESHY_API_KEY"
