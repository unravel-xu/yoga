"""Temporary automated TD integration harness, removed before final TOE save.

For local development only: injected in a COPY of TD's blank NewProject.toe.
No camera or external network is used. Reports are explicit QA output only.
"""
import json
import time
import traceback
from pathlib import Path

_root = Path("/Users/bx/code/Yoga/breathing_garden_td")
_started = False
_last_command = None
_last_poll = 0
_start_time = 0


def rebuild():
    global _started,_start_time
    try:
        namespace = dict(globals())
        namespace["__name__"] = "garden_builder"
        exec(compile((_root/"build_garden_td.py").read_text(),"build_garden_td.py","exec"),namespace)
        garden = op("/project1/garden")
        _started = True
        _start_time = time.perf_counter()
        (_root/"qa"/"build-result.json").write_text(json.dumps({"built":True,"nodes":len(garden.children)},indent=2))
    except Exception:
        error = traceback.format_exc()
        (_root/"qa"/"build-result.json").write_text(json.dumps({"built":False,"error":error},indent=2))
        print(error)


def onStart():
    rebuild()


def onCreate():
    return


def onFrameStart(frame):
    global _last_command,_last_poll
    now = time.perf_counter()
    if now-_last_poll < 1:
        return
    _last_poll = now
    # This development-only poll is never included in the delivered TOE.
    command = _root/"qa"/"command.json"
    if not command.exists():
        return
    text = command.read_text()
    if text == _last_command:
        return
    _last_command = text
    try:
        data = json.loads(text)
        if data["action"] == "rebuild":
            rebuild()
        elif data["action"] == "inspect":
            result = {}
            for path in data["paths"]:
                node = op(path)
                result[path] = {p.name:{"value":str(p.eval()),"menus":list(p.menuNames) if p.isMenu else []} for p in node.pars()} if node else None
            (_root/"qa"/"parameters.json").write_text(json.dumps(result,indent=2))
        elif data["action"] == "exec":
            exec(data["code"],globals())
        elif data["action"] in ("validate","save"):
            garden = op("/project1/garden")
            report = garden.op("validate_garden").module.validate()
            (_root/"qa"/"td-validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
            garden.op("out1").save(str(_root/"qa"/"garden-preview.png"))
            if data["action"] == "save" and report["ok"]:
                # Delete this harness before saving, so the final TOE is self-contained.
                me.destroy()
                project.save(str(_root/"The_Breathing_Garden.toe"))
        (_root/"qa"/"command-result.json").write_text(json.dumps({"ok":True,"action":data["action"]}))
    except Exception:
        (_root/"qa"/"command-result.json").write_text(json.dumps({"ok":False,"error":traceback.format_exc()},indent=2))
