import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TRANSLATIONS = ROOT / "translations"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def leaves(data, prefix=""):
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from leaves(value, path)
        else:
            yield path, value


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.app = self.work / "app"
        self.pack = self.work / "pack"
        save(self.pack / "package.json", {
            "name": "official-pack", "publisher": "ms-ceintl",
            "contributes": {"localizations": [{"translations": []}]},
        })
        save(self.pack / "translations/main.i18n.json", {"contents": {}})
        (self.pack / "translations/extensions").mkdir()

    def run_script(self, name, *args, paths=None):
        overrides = {
            "DIST_DIR": self.work / "dist",
            "CHAT_BUILD_DIR": self.work / "build/chat",
            "EXTRACTED_DIR": self.work / "data/extracted",
            "REPORTS_DIR": self.work / "data/reports",
        }
        overrides.update(paths or {})
        code = "import runpy, sys; from pathlib import Path; "
        code += f"sys.path.insert(0, {str(SCRIPTS)!r}); import _paths; "
        code += " ".join(f"_paths.{key} = Path({str(value)!r});" for key, value in overrides.items())
        code += f" sys.argv = {[str(SCRIPTS / name), *args]!r}; "
        code += f"runpy.run_path({str(SCRIPTS / name)!r}, run_name='__main__')"
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=self.work,
            env={**os.environ, "DEVIN_APP": str(self.app), "VSCODE_ZH_PACK": str(self.pack),
                 "APPDATA": str(self.work / "appdata"), "PYTHONIOENCODING": "utf-8",
                 "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_python_sources_compile(self):
        for directory in (SCRIPTS, ROOT / "tests"):
            for path in directory.glob("*.py"):
                with self.subTest(path=path.name):
                    compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_translation_sources_are_separate_from_outputs(self):
        expected = {
            "core": ["zh_patch.json"],
            "extensions": ["ext_patch.json", "pkg_patch.json", "extjs_patch.json"],
            "chat": [*(f"chat_patch_{i}.json" for i in range(1, 5)), "chat_patch_review.json"],
        }
        for group, names in expected.items():
            for name in names:
                with self.subTest(name=name):
                    self.assertIsInstance(load(TRANSLATIONS / group / name), dict)
        self.assertEqual(list(ROOT.glob("*.py")), [])
        self.assertEqual(list(ROOT.glob("*.json")), [])

    def test_chat_build_from_another_working_directory(self):
        self.run_script("build_chat_dict.py", paths={"EXTRACTED_DIR": ROOT / "data/extracted"})
        expected = {}
        for chunk in sorted((TRANSLATIONS / "chat").glob("chat_patch_[0-9]*.json")):
            expected.update(leaves(load(chunk)))
        self.assertEqual(dict(leaves(load(self.work / "build/chat/chat_zh_translation.json"))), expected)
        self.assertEqual(load(self.work / "build/chat/chat_zh_review.json"),
                         load(TRANSLATIONS / "chat/chat_patch_review.json"))
        self.assertEqual(list(self.work.glob("*.json")), [])

    def test_vsix_build_from_another_working_directory(self):
        self.run_script("build.py")
        vsix = self.work / "dist/zzdevin.devin-language-pack-zh-hans-1.126.0.vsix"
        with zipfile.ZipFile(vsix) as archive:
            self.assertIsNone(archive.testzip())
            package = json.loads(archive.read("extension/package.json"))
            self.assertEqual(package["publisher"], "zzdevin")
            main = json.loads(archive.read("extension/translations/main.i18n.json"))
            self.assertEqual(main["contents"], load(TRANSLATIONS / "core/zh_patch.json"))
            for extension, sections in load(TRANSLATIONS / "extensions/ext_patch.json").items():
                translated = json.loads(archive.read(f"extension/translations/extensions/{extension}.i18n.json"))
                self.assertEqual(translated["contents"], sections)

    def test_analysis_outputs_are_grouped(self):
        save(self.app / "out/nls.metadata.json", {
            "keys": {"module": ["hello"]}, "messages": {"module": ["Hello"]},
        })
        save(self.app / "extensions/example/package.json", {"publisher": "demo", "name": "example"})
        save(self.app / "extensions/example/package.nls.json", {"hello": "Hello"})
        self.run_script("analyze.py")
        self.run_script("analyze_ext.py")
        self.assertEqual(load(self.work / "data/extracted/missing.json"), {"module": {"hello": "Hello"}})
        self.assertIn("demo.example", load(self.work / "data/extracted/ext_missing.json"))
        for name in ("report.txt", "ext_report.txt"):
            self.assertTrue((self.work / "data/reports" / name).is_file())

    def test_extraction_outputs_are_grouped(self):
        for ext in ("windsurf", "windsurf-dev-containers", "windsurf-remote-devin",
                    "windsurf-remote-openssh", "windsurf-remote-wsl"):
            save(self.app / "extensions" / ext / "package.json", {"displayName": "Example Extension"})
        js = self.app / "extensions/windsurf/dist/extension.js"
        js.parent.mkdir(parents=True)
        js.write_text('showInformationMessage("Hello World")', encoding="utf-8")
        chat = self.app / "node_modules/@exa/chat-client/index.js"
        chat.parent.mkdir(parents=True)
        chat.write_text('jn=JSON.parse(\'{"hello":"Hello"}\');jr=JSON.parse(\'{"review":"Review"}\');', encoding="utf-8")
        for name in ("extract_pkg.py", "extract_extjs.py", "extract_dicts.py"):
            self.run_script(name)
        extracted = self.work / "data/extracted"
        self.assertEqual(load(extracted / "pkg_strings.json")["windsurf"], ["Example Extension"])
        self.assertEqual(load(extracted / "extjs_strings.json"), {"dist/extension.js": ["Hello World"]})
        self.assertEqual(load(extracted / "chat_translation_en.json"), {"hello": "Hello"})
        self.assertEqual(load(extracted / "chat_review_en.json"), {"review": "Review"})

    def test_patch_reads_relocated_files_and_remains_idempotent(self):
        pkg = load(TRANSLATIONS / "extensions/pkg_patch.json")
        ext, mapping = next(iter(pkg.items()))
        en, zh = next(iter(mapping.items()))
        package = self.app / "extensions" / ext / "package.json"
        save(package, {"displayName": en})
        js_patches = load(TRANSLATIONS / "extensions/extjs_patch.json")
        rel, mapping = next(iter(js_patches.items()))
        js_en, js_zh = next(iter(mapping.items()))
        js = self.app / rel
        js.parent.mkdir(parents=True, exist_ok=True)
        js.write_text(json.dumps(js_en, ensure_ascii=False), encoding="utf-8")
        chat = self.app / "node_modules/@exa/chat-client/index.js"
        chat.parent.mkdir(parents=True)
        original_chat = 'englishOverrides:JSON.parse(\'{}\')});addResourceBundle("en","translation",t,!0,!0),Uo}'
        chat.write_text(original_chat, encoding="utf-8")
        self.run_script("build_chat_dict.py", paths={"EXTRACTED_DIR": ROOT / "data/extracted"})
        self.run_script("patch_app.py")
        self.assertEqual(load(package)["displayName"], zh)
        self.assertIn(js_zh, js.read_text(encoding="utf-8"))
        self.assertIn('Uo.addResourceBundle("en","review"', chat.read_text(encoding="utf-8"))
        self.assertEqual(Path(str(chat) + ".devin-zh.bak").read_text(encoding="utf-8"), original_chat)
        before = {path: path.read_bytes() for path in (package, js, chat)}
        self.run_script("patch_app.py")
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_legacy_install_reads_relocated_translations(self):
        self.run_script("install.py")
        main = load(self.pack / "translations/main.i18n.json")
        self.assertEqual(main["contents"], load(TRANSLATIONS / "core/zh_patch.json"))
        self.assertTrue((self.pack / "translations/main.i18n.json.devin-zh.bak").is_file())


if __name__ == "__main__":
    unittest.main()
