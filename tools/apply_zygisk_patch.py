#!/usr/bin/env python3
"""
Apply ZygiskFrida de-signature patch with random brand name.
Usage: python3 tools/apply_zygisk_patch.py [--brand BRAND]
"""

import os
import sys
import random
import string
import subprocess
import argparse
import shutil
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ZYGISK_DIR = os.path.join(PROJECT_DIR, "ZygiskFrida")
PATCH_FILE = os.path.join(PROJECT_DIR, "patches", "zygiskfrida.patch")
GADGET_DIR = os.path.join(ZYGISK_DIR, "gadget")

# Architecture mapping: rusda -> ZygiskFrida
ARCH_MAP = {
    "arm": "arm",
    "arm64": "arm64",
    "x86": "x86",
    "x86_64": "x64",
}


def generate_brand(length=5):
    """Generate a random lowercase brand name."""
    consonants = "bcdfghjklmnpqrstvwxyz"
    vowels = "aeiou"
    brand = ""
    for i in range(length):
        if i % 2 == 0:
            brand += random.choice(consonants)
        else:
            brand += random.choice(vowels)
    return brand


def apply_patch():
    """Apply the ZygiskFrida patch."""
    print("[*] Resetting ZygiskFrida...")
    subprocess.run(["git", "checkout", "."], cwd=ZYGISK_DIR, check=True,
                   capture_output=True)

    print("[*] Applying patch...")
    result = subprocess.run(
        ["git", "apply", "--check", PATCH_FILE],
        cwd=ZYGISK_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[!] Patch validation failed: {result.stderr}")
        sys.exit(1)

    subprocess.run(["git", "apply", PATCH_FILE], cwd=ZYGISK_DIR, check=True)
    print("[✓] Patch applied")


def replace_brand(brand):
    """Replace __BRAND__ placeholders with actual brand name."""
    print(f"[*] Replacing __BRAND__ with '{brand}'...")

    # Files to process
    extensions = {".py", ".gradle", ".mk", ".cpp", ".h", ".sh", ".json", ".prop", ".example"}
    skip_dirs = {".git", "build", "xdl", "include", "rapidjson"}

    for root, dirs, files in os.walk(ZYGISK_DIR):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fname in files:
            if not any(fname.endswith(ext) for ext in extensions):
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if "__BRAND__" not in content:
                    continue

                # Replace brand placeholders
                new_content = content.replace("__BRAND__", brand)

                # Also replace lowercase version for header guards
                new_content = new_content.replace("__brand__", brand.lower())

                if new_content != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"  [✓] {os.path.relpath(fpath, ZYGISK_DIR)}")

            except Exception as e:
                print(f"  [!] Error processing {fpath}: {e}")

    print("[✓] Brand replacement complete")


def copy_gadgets(brand, dist_dir=None):
    """Copy rusda-built gadgets to ZygiskFrida/gadget/."""
    if dist_dir is None:
        dist_dir = os.path.join(PROJECT_DIR, "dist-android")

    if not os.path.exists(dist_dir):
        print(f"[!] Distribution directory not found: {dist_dir}")
        print("[!] Please build rusda first: make build && make package")
        sys.exit(1)

    # Find gadget files
    gadget_pattern = os.path.join(dist_dir, f"{brand}-gadget-*.so.xz")
    gadget_files = glob.glob(gadget_pattern)

    if not gadget_files:
        print(f"[!] No gadget files found matching: {gadget_pattern}")
        print("[!] Please build rusda first: make build && make package")
        sys.exit(1)

    # Clean and create gadget directory
    os.makedirs(GADGET_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(GADGET_DIR, "*.so.xz")):
        os.remove(f)

    print(f"[*] Copying gadgets from {dist_dir}...")

    for gadget_file in gadget_files:
        fname = os.path.basename(gadget_file)

        # Extract architecture from filename
        # Expected: {brand}-gadget-{version}-android-{arch}.so.xz
        parts = fname.replace(".so.xz", "").split("-")
        if len(parts) < 5:
            print(f"  [!] Skipping unexpected file: {fname}")
            continue

        arch = parts[-1]  # Last part is architecture

        # Map to ZygiskFrida naming
        magisk_arch = ARCH_MAP.get(arch)
        if magisk_arch is None:
            print(f"  [!] Unknown architecture: {arch}")
            continue

        # Target filename: lib{brand}gadget-{arch}.so.xz (keep lib prefix)
        target_name = f"lib{brand}gadget-{magisk_arch}.so.xz"
        target_path = os.path.join(GADGET_DIR, target_name)

        shutil.copy2(gadget_file, target_path)
        print(f"  [✓] {fname} -> {target_name}")

    print("[✓] Gadget files copied")


def main():
    parser = argparse.ArgumentParser(description="Apply ZygiskFrida patch")
    parser.add_argument("--brand", help="Brand name (auto-generated if not specified)")
    parser.add_argument("--dist-dir", help="Directory containing rusda gadgets")
    parser.add_argument("--skip-gadgets", action="store_true",
                       help="Skip copying gadget files")
    args = parser.parse_args()

    # Validate paths
    if not os.path.exists(ZYGISK_DIR):
        print(f"[!] ZygiskFrida directory not found: {ZYGISK_DIR}")
        sys.exit(1)

    if not os.path.exists(PATCH_FILE):
        print(f"[!] Patch file not found: {PATCH_FILE}")
        sys.exit(1)

    # Generate brand
    brand = args.brand or generate_brand()
    print(f"[*] Using brand: {brand}")

    # Apply patch
    apply_patch()

    # Replace brand
    replace_brand(brand)

    # Copy gadgets
    if not args.skip_gadgets:
        copy_gadgets(brand, args.dist_dir)
    else:
        print("[*] Skipping gadget copy")

    print(f"\n[✓] ZygiskFrida patched with brand '{brand}'")
    print(f"[*] Config directory: /data/local/tmp/{brand}")
    print(f"[*] Gadget name: lib{brand}gadget.so")
    print(f"[*] Module ID: {brand}")
    print(f"[*] Module lib: lib{brand}.so")
    print(f"\n[*] To build: cd ZygiskFrida && ./gradlew :module:assembleZygiskRelease")


if __name__ == "__main__":
    main()
