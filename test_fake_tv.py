"""End-to-end test of backup.py and install.py against a fake LG TV (wss:3001 + icon HTTP server).

Run: python3 test_fake_tv.py   (binds 127.0.0.1:3001 and :8099)
ares-* are replaced by stubs on PATH that record their arguments.
"""
import asyncio
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")

LAUNCH = {"launchPoints": [
    {"id": "netflix", "title": "Netflix", "largeIcon": "http://127.0.0.1:8099/i.png", "iconColor": "#000"},
    {"id": "youtube.leanback.v4", "title": "YouTube", "icon": "http://127.0.0.1:8099/i.png"},
    {"id": "hiddenapp", "title": "Hidden", "hidden": True, "icon": "http://127.0.0.1:8099/i.png"},
], "returnValue": True}
REPLIES = {
    "ssap://com.webos.service.update/getCurrentSWInformation": {
        "returnValue": True, "product_name": "webOS", "model_name": "HE_DTV_W22H_AFADATAA",
        "major_ver": "03", "minor_ver": "21.20", "webos_release": "7.3.0"},
    "ssap://com.webos.applicationManager/listLaunchPoints": LAUNCH,
    "ssap://tv/getExternalInputList": {"returnValue": True, "devices": [{"id": "HDMI_1", "appId": "com.webos.app.hdmi1", "label": "HDMI 1"}]},
    "ssap://settings/getSystemSettings": {"returnValue": True, "category": "option", "settings": {}},
}


class Icon(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(PNG)
    def log_message(self, *a): pass


async def handler(ws):
    async for raw in ws:
        m = json.loads(raw)
        if m["type"] == "register":
            await ws.send(json.dumps({"type": "registered", "id": m["id"], "payload": {"client-key": "KEY123"}}))
        elif m["type"] == "request":
            if m["uri"] in REPLIES:
                await ws.send(json.dumps({"type": "response", "id": m["id"], "payload": REPLIES[m["uri"]]}))
            else:
                await ws.send(json.dumps({"type": "error", "id": m["id"], "error": "404 no such service or method"}))


class FakeTv:
    def __enter__(self):
        d = tempfile.mkdtemp()
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", d + "/k.pem", "-out", d + "/c.pem",
                        "-days", "1", "-subj", "/CN=fake"], check=True, capture_output=True)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(d + "/c.pem", d + "/k.pem")
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()
        def run():
            asyncio.set_event_loop(self.loop)
            async def start():
                self.srv = await websockets.serve(handler, "127.0.0.1", 3001, ssl=ctx)
            self.loop.run_until_complete(start())
            ready.set(); self.loop.run_forever()
        self.t = threading.Thread(target=run, daemon=True); self.t.start(); ready.wait(10)
        self.http = HTTPServer(("127.0.0.1", 8099), Icon)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        return self
    def __exit__(self, *a):
        self.http.shutdown(); self.loop.call_soon_threadsafe(self.loop.stop)


class Kit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tv = FakeTv().__enter__()
        cls.work = tempfile.mkdtemp()
        cls.kit = os.path.join(cls.work, "kit")
        shutil.copytree(HERE, cls.kit, ignore=shutil.ignore_patterns("backup", "build", "__pycache__", ".lgtv-key.json"))
        cls.bin = os.path.join(cls.work, "bin"); os.makedirs(cls.bin)
        cls.log = os.path.join(cls.work, "ares.log")
        for tool in ("package", "install", "launch"):
            p = os.path.join(cls.bin, "ares-" + tool)
            open(p, "w").write(f'#!/bin/sh\necho "{tool} $@" >> "{cls.log}"\n'
                               + ('mkdir -p "$3" && touch "$3/com.gathin.tvhome_1.0.0_all.ipk"\n' if tool == "package" else ""))
            os.chmod(p, 0o755)
        cls.env = dict(os.environ, PATH=cls.bin + os.pathsep + os.environ["PATH"])

    @classmethod
    def tearDownClass(cls):
        cls.tv.__exit__()

    def py(self, script, *args):
        return subprocess.run([sys.executable, os.path.join(self.kit, script), *args], env=self.env,
                              capture_output=True, text=True, timeout=90)

    def test_1_backup(self):
        out = os.path.join(self.work, "bk")
        r = self.py("backup.py", "127.0.0.1", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("firmware 03.21.20", r.stdout)
        self.assertIn("release 7.3.0", r.stdout)
        self.assertIn("3 apps on the Home screen", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(out, "launch-points.json")))
        self.assertIn("Refused", r.stdout)  # system-info etc. are refused by the fake, and reported
        saved = json.load(open(os.path.join(out, "system-info.json")))
        self.assertEqual(saved["type"], "error")

    def test_2_install_dry_run_changes_nothing(self):
        r = self.py("install.py", "--host", "127.0.0.1", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ares-install", r.stdout)
        self.assertFalse(os.path.exists(self.log))
        self.assertFalse(os.path.exists(os.path.join(self.kit, "webos-vibehack", "app", "apps.js")))

    def test_3_install(self):
        r = self.py("install.py", "--host", "127.0.0.1", "--device", "mytv")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        app = os.path.join(self.kit, "webos-vibehack", "app")
        apps = open(os.path.join(app, "apps.js")).read()
        self.assertIn('"netflix"', apps); self.assertNotIn("hiddenapp", apps)
        self.assertIn("com.webos.app.hdmi1", apps)
        for f in ("icon.png", "largeIcon.png"):
            self.assertTrue(os.path.getsize(os.path.join(app, f)) > 0)
        from PIL import Image
        self.assertEqual(Image.open(os.path.join(app, "icon.png")).size, (80, 80))
        self.assertEqual(Image.open(os.path.join(app, "largeIcon.png")).size, (130, 130))
        log = open(self.log).read().splitlines()
        self.assertEqual([l.split()[0] for l in log], ["package", "install", "launch"])
        self.assertIn("-d mytv", log[1]); self.assertIn("com.gathin.tvhome_1.0.0_all.ipk", log[1])
        self.assertTrue(log[2].endswith("com.gathin.tvhome"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
