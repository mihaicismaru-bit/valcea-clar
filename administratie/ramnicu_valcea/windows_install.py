"""Task Scheduler installation without changing any PowerShell execution policy."""
from __future__ import annotations

import argparse
from datetime import datetime, time
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
import xml.etree.ElementTree as ET

from .collector import now
from .windows_runtime import write_json

TASK_NAME = "ValceaClar-Ramnicu-Daily"
NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def task_xml(root, executable, identity, daily="07:15"):
    at = datetime.strptime(daily, "%H:%M").time()
    boundary = datetime.combine(datetime.now().date(), at).isoformat()
    ET.register_namespace("", NS)
    task = ET.Element("{" + NS + "}Task", version="1.2")
    def node(parent, name, value=None, **attributes):
        item = ET.SubElement(parent, "{" + NS + "}" + name, **attributes)
        if value is not None:
            item.text = str(value)
        return item
    info = node(task, "RegistrationInfo")
    node(info, "Author", "ValceaClar")
    node(info, "Description", "ValceaClar managed collection and verified local backup. No publishing.")
    triggers = node(task, "Triggers")
    trigger = node(triggers, "CalendarTrigger")
    node(trigger, "StartBoundary", boundary)
    node(trigger, "Enabled", "true")
    node(node(trigger, "ScheduleByDay"), "DaysInterval", "1")
    principal = node(node(task, "Principals"), "Principal", id="Author")
    node(principal, "UserId", identity)
    node(principal, "LogonType", "InteractiveToken")
    node(principal, "RunLevel", "LeastPrivilege")
    settings = node(task, "Settings")
    for name, value in [
        ("MultipleInstancesPolicy", "IgnoreNew"), ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"), ("StartWhenAvailable", "true"),
        ("Enabled", "true"), ("ExecutionTimeLimit", "PT1H")]:
        node(settings, name, value)
    action = node(node(task, "Actions", Context="Author"), "Exec")
    node(action, "Command", str(executable))
    node(action, "Arguments", '-m administratie.ramnicu_valcea.windows_runtime run --root "' + str(root) + '"')
    node(action, "WorkingDirectory", str(root))
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


def install(root, daily="07:15", python=None):
    root = Path(root).resolve()
    control = root / "runtime" / "windows"
    control.mkdir(parents=True, exist_ok=True)
    record = {"installed_at": now(), "task": TASK_NAME, "root": str(root),
              "status": "PREPARING", "registered": False}
    try:
        if os.name != "nt":
            raise RuntimeError("Installation requires Windows")
        if sys.version_info < (3, 12):
            raise RuntimeError("Python 3.12+ required")
        executable = root / ".venv" / "Scripts" / "pythonw.exe"
        if not executable.is_file():
            venv.EnvBuilder(with_pip=False, system_site_packages=True).create(root / ".venv")
        if not executable.is_file():
            raise RuntimeError("Local Python environment has no pythonw.exe")
        record["python"] = str(executable)
        identity = subprocess.run(["whoami.exe"], capture_output=True, text=True, check=True).stdout.strip()
        # Never replace an unrelated task with the same name.
        query = subprocess.run(["schtasks.exe", "/Query", "/TN", TASK_NAME, "/XML"],
                               capture_output=True, text=True)
        if query.returncode == 0:
            existing = ET.fromstring(query.stdout)
            if existing.findtext("{" + NS + "}RegistrationInfo/{" + NS + "}Author") != "ValceaClar":
                raise RuntimeError("Task name belongs to an unmanaged task")
        definition = control / "daily-task.xml"
        definition.write_bytes(task_xml(root, executable, identity, daily))
        created = subprocess.run(["schtasks.exe", "/Create", "/TN", TASK_NAME, "/XML", str(definition), "/F"],
                                 capture_output=True, text=True)
        if created.returncode:
            raise RuntimeError((created.stderr or created.stdout).strip()[:1000])
        verified = subprocess.run(["schtasks.exe", "/Query", "/TN", TASK_NAME, "/XML"],
                                  capture_output=True, text=True, check=True)
        actual = ET.fromstring(verified.stdout)
        if actual.findtext(".//{" + NS + "}Command") != str(executable):
            raise RuntimeError("Registered task command does not match installed runtime")
        record.update(status="REGISTERED", registered=True, daily_at_local=daily,
                      logon_type="InteractiveToken: Windows user must remain signed in")
        started = subprocess.run(["schtasks.exe", "/Run", "/TN", TASK_NAME], capture_output=True, text=True)
        record["first_run_requested"] = started.returncode == 0
        if started.returncode:
            record.update(status="REGISTERED_START_FAILED", error=(started.stderr or started.stdout).strip()[:1000])
    except Exception as exc:
        record.update(status="INSTALL_FAILED", error=str(exc)[:1000])
    write_json(control / "scheduler.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--daily-at", default="07:15")
    args = parser.parse_args()
    result = install(args.root, args.daily_at)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "REGISTERED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
