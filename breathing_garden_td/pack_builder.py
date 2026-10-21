"""Mechanically package readable sources into a single paste-and-run TD script."""
import base64
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent
FILES = ("garden_engine.py","garden_runtime.py","branches_sop_callbacks.py",
         "frame_execute_callbacks.py","reset_controls.py","validate_garden_td.py",
         "stage3_tracking_adapter.py")


def generate():
    sources = {name:(HERE/name).read_text(encoding="utf-8") for name in FILES}
    payload = base64.b85encode(zlib.compress(json.dumps(sources,ensure_ascii=False).encode("utf-8"),9)).decode("ascii")
    template = (HERE/"builder_template.py").read_text(encoding="utf-8")
    # Generated artifact, not hand-edited. No absolute paths or external imports.
    output = ('"""自包含 TD builder。复制完整内容到 Text DAT，Run Script。\n'
              '由 pack_builder.py 生成；内置纯 Python 引擎与全部回调，无外部文件依赖。"""\n'
              'import base64, json, zlib\n\n'+template+'\n\n'
              '_PAYLOAD = '+repr(payload)+'\n'
              'def embedded_sources():\n'
              '    return json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)).decode("utf-8"))\n\n'
              '# TD Text DAT Run Script does not use __name__ == "__main__".\n'
              'try:\n'
              '    import td as _td\n'
              'except ImportError:\n'
              '    pass  # ordinary Python may inspect/compile this artifact\n'
              'else:\n'
              '    build(embedded_sources())\n')
    (HERE/"build_garden_td.py").write_text(output,encoding="utf-8")
    print("Generated self-contained builder:",len(output.encode("utf-8")),"bytes")


if __name__ == "__main__":
    generate()
