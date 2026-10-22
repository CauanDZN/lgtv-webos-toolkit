#!/usr/bin/env python3
"""Windows-friendly replacement for webos-vibehack/install.sh (which needs macOS `sips`).

    python install.py --host 192.168.10.182            # sync apps, package, install, launch
    python install.py --host 192.168.10.182 --dry-run  # print what it would run, change nothing

Run lg-webos/README.md "Passo 3" first: the TV must be in Developer Mode and registered with
ares-setup-device under the name given by --device (default: lgtv).
Needs: Node.js (for LG's ares CLI, fetched with npx if missing), pip install websockets pillow
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "webos-vibehack")
APP_ID = "com.gathin.tvhome"


def ares_cmd(tool):
    """Command prefix for an ares tool: the installed one, otherwise npx."""
    found = shutil.which("ares-" + tool)
    if found:
        return [found]
    npx = shutil.which("npx")
    if not npx:
        sys.exit("Node.js not found: install it from nodejs.org, then run this again.")
    return [npx, "-y", "-p", "@webos-tools/cli", "ares-" + tool]


def run(cmd, dry, cwd=SRC):
    print("$", " ".join(cmd))
    if dry:
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def make_icons(dry):
    """webOS wants PNG icons at 80px and 130px; install.sh used macOS `sips` for this."""
    small, large = os.path.join(SRC, "app", "icon.png"), os.path.join(SRC, "app", "largeIcon.png")
    if os.path.exists(small) and os.path.exists(large):
        return
    print("making app/icon.png and app/largeIcon.png from assets/icon.jpg")
    if dry:
        return
    from PIL import Image
    img = Image.open(os.path.join(SRC, "assets", "icon.jpg")).convert("RGB")
    img.resize((80, 80), Image.LANCZOS).save(small)
    img.resize((130, 130), Image.LANCZOS).save(large)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="TV IP address")
    ap.add_argument("--device", default="lgtv", help="name given to ares-setup-device")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run([sys.executable, "sync-apps.py", args.host], args.dry_run)
    make_icons(args.dry_run)

    build = os.path.join(SRC, "build")
    if not args.dry_run:
        shutil.rmtree(build, ignore_errors=True)
        os.makedirs(build)
    run(ares_cmd("package") + ["app", "-o", "build"], args.dry_run)
    ipks = glob.glob(os.path.join(build, APP_ID + "_*.ipk"))
    if not ipks and not args.dry_run:
        sys.exit("ares-package produced no .ipk in build/")
    ipk = os.path.join("build", os.path.basename(ipks[0])) if ipks else f"build/{APP_ID}_1.0.0_all.ipk"
    run(ares_cmd("install") + ["-d", args.device, ipk], args.dry_run)
    run(ares_cmd("launch") + ["-d", args.device, APP_ID], args.dry_run)
    print("Done. To undo: ares-install -d", args.device, "-r", APP_ID)


if __name__ == "__main__":
    main()
