"""Create a separate blank TD test project using the official local template."""
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
BIN = Path("/Applications/TouchDesigner.app/Contents/MacOS")


def main():
    folder = HERE/"qa"/"bootstrap"
    folder.mkdir(parents=True,exist_ok=True)
    target = folder/"Garden_QA.toe"
    if target.exists():
        raise RuntimeError("QA project exists; use its command.json channel instead of overwriting it.")
    shutil.copy2(BIN.parent/"Resources/tfs/Samples/Setup/Base/NewProject.toe",target)
    subprocess.run([str(BIN/"toeexpand"),str(target)],check=False)
    expanded = Path(str(target)+".dir")
    toc = Path(str(target)+".toc")
    # Some templates don't have /project1 yet. Create its minimal Base COMP.
    comp = expanded/"project1"
    comp.mkdir(exist_ok=True)
    if not (expanded/"project1.n").exists():
        (expanded/"project1.n").write_text("COMP:base\ntile 0 0 100 100\nend\n")
        (expanded/"project1.parm").write_text("?\n?\n")
        toc.write_text(toc.read_text()+"project1.n\nproject1.parm\n")
    (comp/"garden_qa.n").write_text("DAT:execute\ntile 0 0 280 205\nflags = viewer 1 parlanguage 0\nend\n")
    # Use a real external DAT file ONLY for this temporary harness.
    source = (HERE/"qa_bootstrap.py").as_posix()
    (comp/"garden_qa.parm").write_text('?\nstart 67108864 on\nframestart 67108864 on\nfile 67108864 "'+source+'"\nsyncfile 67108864 on\nlanguage 67108864 python\n?\n')
    toc.write_text(toc.read_text()+"project1/garden_qa.n\nproject1/garden_qa.parm\n")
    target.unlink()  # exact disposable generated copy, never a user's TOE
    subprocess.run([str(BIN/"toecollapse"),str(target)],check=True)
    print(target)


if __name__ == "__main__":
    main()
