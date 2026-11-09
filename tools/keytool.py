#!/usr/bin/env python3
"""Local web UI for finding the iOS *backup* password by trial.

Starts a server on http://127.0.0.1:<port> with a form. Each attempt tests the
password against the backup's keybag (PBKDF2 with ~10M iterations, a few seconds
per try). On success it extracts the Dead Cells files automatically.

The password is never written to disk; it lives in memory only for the duration
of the test. Run standalone or via ``dcsync keytool <backup_dir>``.
"""
import http.server
import json
import os
import plistlib
import subprocess
import sys
import threading
import time

# Allow running as a standalone script (python tools/keytool.py ...).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deadcells_save import ios_backup  # noqa: E402


PAGE = """<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Dead Cells - iOS backup password</title>
<style>
 body{font:16px/1.5 -apple-system,system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 20px;background:#141416;color:#e7e7ea}
 h1{font-size:20px} code{background:#26262b;padding:2px 6px;border-radius:5px}
 input,textarea{font-size:17px;padding:10px 12px;width:100%;box-sizing:border-box;border-radius:8px;border:1px solid #3a3a42;background:#1d1d21;color:#fff}
 textarea{height:70px}
 button{font-size:16px;padding:10px 18px;margin-top:10px;border-radius:8px;border:0;background:#c0392b;color:#fff;cursor:pointer}
 button:disabled{opacity:.5}
 .row{margin:18px 0}
 .ok{color:#6fcf7f} .bad{color:#e57373} .wait{color:#e0b050}
 ul{padding-left:18px} li{font-family:ui-monospace,monospace;font-size:13px}
 .hint{color:#9a9aa2;font-size:13px}
</style>
<h1>&#128273; iOS backup password</h1>
<p class=hint>The password you set in Finder/iTunes for <em>"Encrypt local backup"</em>.
This is NOT the device passcode. Each attempt takes a few seconds.</p>
<div class=row>
 <input id=pw type=password placeholder="a password" autofocus autocomplete=off>
 <button id=go onclick=one()>Try</button>
 <button onclick="pw.type=pw.type=='password'?'text':'password'" style="background:#3a3a42">&#128065;</button>
</div>
<div class=row>
 <p class=hint>Several candidates? One per line, tried in order:</p>
 <textarea id=list placeholder="password1&#10;Password2!&#10;an old one"></textarea>
 <button onclick=many()>Try the list</button>
</div>
<div id=status class=row></div>
<div id=result class=row></div>
<script>
const S=(t,c)=>{status.innerHTML='<span class="'+c+'">'+t+'</span>'}
async function attempt(pw){
 const r=await fetch('/try',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pw})})
 return r.json()
}
async function one(){
 const v=pw.value; if(!v)return; go.disabled=true; S('Trying... (a few seconds)','wait')
 const j=await attempt(v); go.disabled=false; render(j)
}
async function many(){
 const lines=list.value.split('\\n').map(s=>s.trim()).filter(Boolean)
 for(let i=0;i<lines.length;i++){ S('Trying '+(i+1)+'/'+lines.length,'wait')
  const j=await attempt(lines[i]); if(j.ok){render(j);return} }
 S('None of the list worked.','bad')
}
function render(j){
 if(j.ok){ S('&#9989; Correct! Extracting Dead Cells...','ok')
  let h='<h3 class=ok>Extracted files ('+j.files.length+'):</h3><ul>'
  for(const f of j.files) h+='<li>'+f+'</li>'
  h+='</ul><p class=ok>Done. Back to the terminal to continue.</p>'; result.innerHTML=h
 } else { S('&#10060; Not that one. Try another.','bad') }
}
</script>
</html>"""


def run(backup_dir, out_dir="extracted", port=8777):
    with open(os.path.join(backup_dir, "Manifest.plist"), "rb") as fh:
        keybag_blob = plistlib.load(fh)["BackupKeyBag"]

    state = {"done": None}

    def test_pw(pw):
        from iphone_backup_decrypt import google_iphone_dataprotection as gidp
        return bool(gidp.Keybag(keybag_blob).unlockWithPassphrase(pw.encode("utf-8")))

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            b = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            self._send(200, PAGE) if self.path in ("/", "/index.html") else self._send(404, "no")

        def do_POST(self):
            if self.path != "/try":
                return self._send(404, "no")
            n = int(self.headers.get("Content-Length", 0))
            pw = json.loads(self.rfile.read(n) or b"{}").get("pw", "")
            t0 = time.time()
            ok = False
            try:
                ok = test_pw(pw)
            except Exception as exc:  # noqa: BLE001
                print("  error:", exc)
            print("  attempt (%d chars) -> %s (%.1fs)" % (len(pw), "OK" if ok else "no", time.time() - t0))
            if not ok:
                return self._send(200, json.dumps({"ok": False}), "application/json")
            files = ios_backup.extract(backup_dir, pw, out_dir)
            state["done"] = files
            self._send(200, json.dumps({"ok": True, "files": files}), "application/json")

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    url = "http://127.0.0.1:%d" % port
    print("Password UI:", url)
    print("Backup:", backup_dir, "| output:", out_dir)
    print("(Ctrl-C to stop)\n")
    if sys.platform == "darwin":
        # url is a fixed localhost address we build ourselves (int port); pass as arg list.
        threading.Thread(
            target=lambda: (time.sleep(0.6), subprocess.run(["open", url], check=False)),
            daemon=True,
        ).start()
    try:
        while state["done"] is None:
            srv.handle_request()
    except KeyboardInterrupt:
        return None
    print("\nExtracted:")
    for f in state["done"]:
        print("  ", f)
    srv.timeout = 1
    for _ in range(3):
        srv.handle_request()
    return state["done"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: keytool.py <backup_dir> [out_dir] [port]")
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "extracted",
        int(sys.argv[3]) if len(sys.argv) > 3 else 8777)
