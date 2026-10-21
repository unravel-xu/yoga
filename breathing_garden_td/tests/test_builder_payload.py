"""Static packaging checks, separate from actual TD integration tests."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuilderPackagingTests(unittest.TestCase):
    def test_all_sources_compile(self):
        for path in ROOT.glob("*.py"):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"),filename=str(path))

    def test_embedded_sources_match_delivered_files(self):
        spec = importlib.util.spec_from_file_location("garden_builder",ROOT/"build_garden_td.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sources = module.embedded_sources()
        self.assertGreaterEqual(len(sources),7)
        for name,text in sources.items():
            with self.subTest(source=name):
                self.assertEqual(text,(ROOT/name).read_text(encoding="utf-8"))
                ast.parse(text)
        builder = (ROOT/"build_garden_td.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/bx/",builder)
        self.assertNotIn("read_text(",builder)
        self.assertNotIn("open(",builder)


if __name__ == "__main__":
    unittest.main()
