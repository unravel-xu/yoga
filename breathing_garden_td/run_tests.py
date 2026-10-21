"""Run standard-library tests and save an explicit machine-readable QA report."""
import json
from pathlib import Path
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent


def main():
    sys.path.insert(0,str(HERE.parent))
    suite = unittest.defaultTestLoader.discover(str(HERE/"tests"))
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"passed":result.wasSuccessful(),"tests":result.testsRun,
              "seconds":time.perf_counter()-started,"python":sys.version,
              "failures":[str(t) for t,_ in result.failures],
              "errors":[str(t) for t,_ in result.errors],
              "scope":"Python engine and static builder checks; TD tests are reported separately."}
    (HERE/"qa").mkdir(exist_ok=True)
    (HERE/"qa"/"python-tests.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
