"""Run on the authorized VM. Upgrade one demo terminal, never all Wine processes.

Inputs are staged MQ5/EX5 plus a hash-verified manifest. No credentials read.
"""
import argparse
import ctypes as C
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BASE = Path("/home/ubuntu/.wine/drive_c/Program Files/MetaTrader 5 V16.59 V22 New Demo")
WIN_EXE = "C:/Program Files/MetaTrader 5 V16.59 V22 New Demo/terminal64.exe"
ACCOUNT = 5056497798
OLD_SHA = "E5B725EC83945B9E2126B72978E02A2EFCA28EC33AD649E575B4F5E2F4021AC0"
CHARTS = ("MQL5/Profiles/Charts/Default/chart01.chr", "Profiles/Charts/Default/chart01.chr")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def proc_args():
    result = {}
    for p in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            a = p.read_bytes().decode(errors="replace").strip("\0").split("\0")
        except (OSError, ProcessLookupError):
            continue
        if a and a[0].replace("\\", "/").lower() == WIN_EXE.lower():
            result[int(p.parent.name)] = a
    return result


def terminal_pids():
    # For verifying preservation of every other terminal, not stopping them.
    result = []
    for p in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            a = p.read_bytes().decode(errors="replace").split("\0")[0]
            if a.lower().startswith("c:") and a.lower().endswith("terminal64.exe"):
                result.append(int(p.parent.name))
        except OSError:
            pass
    return sorted(result)


def titles(pid):
    env = dict(os.environ, DISPLAY=":0")
    p = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)],
                       env=env, text=True, capture_output=True)
    result = []
    for w in p.stdout.split():
        title = subprocess.check_output(["xdotool", "getwindowname", w], env=env, text=True).strip()
        if title:
            result.append(dict(window=int(w), title=title))
    return result


def chart_text(p):
    raw = p.read_bytes()
    if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("Expected BOM-encoded chart")
    return raw.decode("utf-16")


def inspect():
    processes = proc_args()
    if len(processes) != 1:
        raise ValueError("Expected exactly one target terminal")
    pid, args = next(iter(processes.items()))
    windows = [w for w in titles(pid) if re.search(r"\b"+str(ACCOUNT)+r"\b", w["title"])
               and "MetaQuotes-Demo" in w["title"] and "Demo Account" in w["title"]]
    if len(windows) != 1:
        raise ValueError("Cannot verify current demo account in main-window title")
    active = list((BASE / "MQL5/Profiles/Charts/Default").glob("*.chr"))
    experts = [(p.name, chart_text(p)) for p in active if "<expert>" in chart_text(p)]
    if len(experts) != 1:
        raise ValueError("Expected one attached expert in target profile")
    t = chart_text(BASE / CHARTS[0])
    for token in ("name=AegisPredator_v23", "symbol=XAUUSD", "period_size=1",
                  f"InpTargetAccount={ACCOUNT}", "InpMagicNumber=992300", "InpLotSize=0.01",
                  "InpStopLossATRMul=1.5", "InpTakeProfitRRMul=2.0", "InpATRPeriod=14",
                  "InpMinSLPoints=150", "InpMaxHoldBars=60", "InpDonchianPeriod=20",
                  "InpEnableHardSL=true", "InpEnableMarginGuard=true", "InpEnableSessionGuard=false",
                  "InpEnableSpreadGuard=false", "InpEnableCircuitBreaker=true",
                  "InpMaxConsecutiveLosses=4", "InpCooldownMinutes=90"):
        if token not in t:
            raise ValueError("Target chart identity/settings mismatch: "+token)
    if digest(BASE / "MQL5/Experts/AegisPredator_v23.ex5") != OLD_SHA:
        raise ValueError("Original VM expert binary changed since baseline verification")
    return dict(pid=pid, arguments=args[1:], window=windows[0], other_terminal_pids=[p for p in terminal_pids() if p != pid],
                charts=[c for c in CHARTS if (BASE / c).exists()])


def close_gracefully(window):
    # ICCCM WM_DELETE_WINDOW asks Wine/MT5 to save and exit. Not XDestroyWindow.
    class Data(C.Union):
        _fields_ = [("b", C.c_char*20), ("s", C.c_short*10), ("l", C.c_long*5)]
    class Message(C.Structure):
        _fields_ = [("type",C.c_int),("serial",C.c_ulong),("send_event",C.c_int),
                    ("display",C.c_void_p),("window",C.c_ulong),("message_type",C.c_ulong),
                    ("format",C.c_int),("data",Data)]
    class Event(C.Union):
        _fields_ = [("xclient",Message),("pad",C.c_long*24)]
    x = C.CDLL("libX11.so.6")
    x.XOpenDisplay.argtypes=[C.c_char_p]; x.XOpenDisplay.restype=C.c_void_p
    x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int]; x.XInternAtom.restype=C.c_ulong
    x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(Event)]
    x.XFlush.argtypes=[C.c_void_p]; x.XCloseDisplay.argtypes=[C.c_void_p]
    protocol = subprocess.check_output(["xprop","-id",str(window),"WM_PROTOCOLS"],
                                     env=dict(os.environ,DISPLAY=":0"),text=True)
    if "WM_DELETE_WINDOW" not in protocol:
        raise ValueError("Main window does not support graceful close")
    display=x.XOpenDisplay(b":0")
    if not display:
        raise ValueError("Cannot access display")
    try:
        event=Event(); event.xclient.type=33; event.xclient.send_event=1
        event.xclient.display=display; event.xclient.window=window
        event.xclient.message_type=x.XInternAtom(display,b"WM_PROTOCOLS",0)
        event.xclient.format=32
        event.xclient.data.l[0]=x.XInternAtom(display,b"WM_DELETE_WINDOW",0)
        event.xclient.data.l[1]=0
        if not x.XSendEvent(display,window,0,0,C.byref(event)):
            raise ValueError("Graceful-close request failed")
        x.XFlush(display)
    finally:
        x.XCloseDisplay(display)


def patch_chart(text):
    for token in (f"InpTargetAccount={ACCOUNT}", "InpMagicNumber=992300", "InpLotSize=0.01",
                  "InpStopLossATRMul=1.5", "InpTakeProfitRRMul=2.0", "InpEnableCircuitBreaker=true",
                  "InpMaxConsecutiveLosses=4", "InpCooldownMinutes=90"):
        if token not in text:
            raise ValueError("Chart changed during graceful shutdown: "+token)
    for old,new in (("name=AegisPredator_v23", "name=AegisPredator_v24"),
                    ("path=Experts\\AegisPredator_v23.ex5", "path=Experts\\AegisPredator_v24.ex5"),
                    ("InpFadeBreakouts=true", "InpFadeBreakouts=false")):
        if text.count(old) != 1:
            raise ValueError("Expected exactly one chart replacement: "+old)
        text=text.replace(old,new,1)
    return text


def apply(stage):
    manifest=json.loads((stage / "manifest.json").read_text())
    if manifest["account"] != ACCOUNT or not manifest["native_parity_passed"]:
        raise ValueError("Deployment manifest not authorized/verified")
    for name,key in (("AegisPredator_v24.mq5","source_sha"),("AegisPredator_v24.ex5","binary_sha")):
        if digest(stage / name) != manifest[key]:
            raise ValueError("Staged artifact hash mismatch")
        if (BASE / "MQL5/Experts" / name).exists():
            raise ValueError("V24 file already exists; do not overwrite unknown deployment")
    snapshot=inspect()
    arguments=snapshot["arguments"]
    if any(not (a=="/portable" or a.startswith("/skipupdate")) for a in arguments):
        raise ValueError("Unexpected original launch options")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup=BASE / "v24_upgrade_backups" / stamp
    backup.mkdir(parents=True,exist_ok=False)
    for i,c in enumerate(snapshot["charts"]):
        shutil.copy2(BASE/c,backup/f"before_{i}.chr")
    for suffix in ("mq5","ex5"):
        original=BASE / f"MQL5/Experts/AegisPredator_v23.{suffix}"
        if original.exists():
            shutil.copy2(original,backup/original.name)
    snapshot["backup"]=str(backup)
    (backup / "preflight.json").write_text(json.dumps(snapshot,indent=2))
    # Capture append offsets, never truncate terminal/expert journals.
    offsets={str(p):p.stat().st_size for folder in (BASE/"logs",BASE/"MQL5/logs") for p in folder.glob("*.log")}
    close_gracefully(snapshot["window"]["window"])
    for _ in range(80):
        if snapshot["pid"] not in proc_args():
            break
        time.sleep(.25)
    if snapshot["pid"] in proc_args():
        raise RuntimeError("Terminal did not exit gracefully. No forced kill or chart replacement performed.")
    if snapshot["other_terminal_pids"] != terminal_pids():
        raise ValueError("Other-terminal PID inventory changed; stop before replacement")
    for name in ("AegisPredator_v24.mq5","AegisPredator_v24.ex5"):
        shutil.copy2(stage/name,BASE/"MQL5/Experts"/name)
    for i,c in enumerate(snapshot["charts"]):
        p=BASE/c
        shutil.copy2(p,backup/f"after_close_{i}.chr")
        text=patch_chart(chart_text(p))
        tmp=p.with_suffix(".v24tmp")
        tmp.write_bytes(text.encode("utf-16"))
        os.replace(tmp,p)
    env=dict(os.environ,DISPLAY=":0",WINEPREFIX="/home/ubuntu/.wine",WINEDLLOVERRIDES="mscoree,mshtml=")
    logpath=BASE/f"v24_launch_{stamp}.log"
    with logpath.open("ab") as out:
        launcher=subprocess.Popen(["wine",str(BASE/"terminal64.exe")]+arguments,cwd=BASE,env=env,
                                  stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
    result=dict(snapshot=snapshot,launcher_pid=launcher.pid,launch_log=str(logpath),manifest=manifest,status="LAUNCHED_NOT_YET_VERIFIED")
    (backup/"deployment.json").write_text(json.dumps(result,indent=2))
    for _ in range(90):
        logs=[]
        for folder in (BASE/"logs",BASE/"MQL5/logs"):
            for p in folder.glob("*.log"):
                raw=p.read_bytes()[offsets.get(str(p),0):]
                if raw:
                    logs += raw.decode("utf-16-le",errors="replace").splitlines()
        health=[line for line in logs if f"V24 HEALTH Account={ACCOUNT} Mode=DEMO" in line]
        failures=[line for line in logs if "V24 BLOCKED" in line or "AegisPredator_v24" in line and "initialization failed" in line]
        if failures:
            result["failures"]=failures
            break
        if health and all(token in health[-1] for token in ("Connected=1","AutoTrading=1","EAAllowed=1","AccountTrading=1","AccountExperts=1")):
            result.update(status="VERIFIED",health=health[-1],target_pids=list(proc_args()),
                          v24_log_tail=[line for line in logs if "V24" in line or "AegisPredator_v24" in line][-12:])
            break
        time.sleep(.5)
    result["other_terminal_pids_after"]=[p for p in terminal_pids() if p not in proc_args()]
    if result["other_terminal_pids_after"] != snapshot["other_terminal_pids"]:
        result["status"]="OTHER_TERMINAL_INVENTORY_CHANGED"
    for name,key in (("AegisPredator_v24.mq5","source_sha"),("AegisPredator_v24.ex5","binary_sha")):
        if digest(BASE/"MQL5/Experts"/name) != manifest[key]:
            result["status"]="DEPLOYED_HASH_MISMATCH"
    (backup/"deployment.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    if result["status"] != "VERIFIED":
        raise RuntimeError("Deployment not verified. Preserve backup and inspect target, no success claim.")


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("inspect","apply"))
    p.add_argument("--stage",type=Path)
    a=p.parse_args()
    if a.action=="inspect":
        print(json.dumps(inspect(),indent=2))
    elif a.stage:
        apply(a.stage.resolve())
    else:
        p.error("--stage required")
