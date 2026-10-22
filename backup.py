#!/usr/bin/env python3
"""Snapshot an LG webOS TV's current state before you change anything.

    python backup.py 192.168.10.182

Saves raw JSON under backup/<timestamp>/ next to this script: firmware/model, every app on the
Home screen (the list to compare against after a cleanup), HDMI inputs, and the settings
categories the TV is willing to return. Read-only: it never writes a setting on the TV.

The first run shows a pairing prompt on the TV: accept it with the remote.
Needs: pip install websockets
"""
import asyncio
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "webos-vibehack"))

import lgtv  # noqa: E402  (the reviewed pairing helper from webos-vibehack)

# name -> (uri, payload). Each one is best effort: firmware differs and some refuse.
QUERIES = {
    "software-info": ("ssap://com.webos.service.update/getCurrentSWInformation", {}),
    "system-info": ("ssap://system/getSystemInfo", {}),
    "launch-points": ("ssap://com.webos.applicationManager/listLaunchPoints", {}),
    "apps": ("ssap://com.webos.applicationManager/listApps", {}),
    "external-inputs": ("ssap://tv/getExternalInputList", {}),
    "foreground-app": ("ssap://com.webos.applicationManager/getForegroundAppInfo", {}),
}
SETTING_CATEGORIES = ["option", "network", "picture", "sound", "time", "lock", "general"]


async def ask(ws, rid, uri, payload):
    """Send one request and return the whole reply (type, payload, error), not only the payload."""
    await ws.send(json.dumps({"type": "request", "id": rid, "uri": uri, "payload": payload}))
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        if msg.get("id") == rid:
            return msg


async def main(host, outdir):
    ws = await lgtv.session(host)
    results = {}
    try:
        jobs = dict(QUERIES)
        for cat in SETTING_CATEGORIES:
            jobs["settings-" + cat] = ("ssap://settings/getSystemSettings", {"category": cat})
        for i, (name, (uri, payload)) in enumerate(jobs.items()):
            try:
                msg = await ask(ws, f"b{i}", uri, payload)
            except asyncio.TimeoutError:
                msg = {"type": "error", "error": "timeout"}
            results[name] = msg
    finally:
        await ws.close()

    os.makedirs(outdir, exist_ok=True)
    ok, failed = [], []
    for name, msg in results.items():
        with open(os.path.join(outdir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(msg, f, indent=1, ensure_ascii=False)
        good = msg.get("type") != "error" and msg.get("payload", {}).get("returnValue", True) is not False
        (ok if good else failed).append(name)

    sw = results.get("software-info", {}).get("payload", {})
    print(f"Saved to {outdir}")
    if sw:
        print(f"Model: {sw.get('model_name', '?')} | {sw.get('product_name', '?')} | "
              f"firmware {sw.get('major_ver', '?')}.{sw.get('minor_ver', '?')} | "
              f"release {sw.get('webos_release', '?')}")
    else:
        print("Model/firmware: the TV refused software-info; read it in Settings > General > About this TV.")
    print(f"Answered: {', '.join(ok) or 'nothing'}")
    if failed:
        print(f"Refused or empty (normal on some firmware): {', '.join(failed)}")
    launch = results.get("launch-points", {}).get("payload", {}).get("launchPoints", [])
    print(f"{len(launch)} apps on the Home screen recorded.")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: backup.py <TV IP> [output dir]")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "backup", stamp)
    asyncio.run(main(sys.argv[1], out))
