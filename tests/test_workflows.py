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
            "chat": [*(f"chat_patch_{i}.json" for i in range(1, 6)), "chat_patch_review.json"],
            "app": ["ui_patch.json"],
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
        original_chat = ('englishOverrides:JSON.parse(\'{}\')});'
                         't&&Uo.addResourceBundle("en","translation",t,!0,!0),Uo}')
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

    def _make_chat_bundle(self, tail):
        return ('englishOverrides:JSON.parse(\'{"transcript":{"keepMe":"ORIG"}}\')});'
                + tail
                + '"Available with Pro",x="Off",label:"Off",category:"Off",id:"Off",'
                  'labelKey:"Off",y==="Off",z:"Off",w:{"Off":1},label:"Daily quota usage"'
                + 'useOnboardingBridges must be used inside <OnboardingBridgeProvider> "Off"')

    def test_bundle_pipeline_covers_all_chat_copies(self):
        paths = {}
        for rel, tail in (
            ("node_modules/@exa/chat-client/index.js",
             't&&Uo.addResourceBundle("en","translation",t,!0,!0),Uo}'),
            ("out/vs/workbench/windsurf-chat-client/index.js",
             't&&Uo.addResourceBundle("en","translation",t,!0,!0),Uo}'),
            ("out/vs/sessions/sessions.desktop.main.js",
             'o&&RL.addResourceBundle("en","translation",o,!0,!0),RL}'),
        ):
            f = self.app / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(self._make_chat_bundle(tail), encoding="utf-8")
            paths[rel] = f
        wb = self.app / "out/vs/workbench/workbench.desktop.main.js"
        wb.parent.mkdir(parents=True, exist_ok=True)
        wb.write_text('q="On";getWorkspaceSettings(){return[{id:"x",label:"On",'
                      'category:"User Interface",label:"Daily quota usage"}]}'
                      '_readNativeStorageCompletionMode(){let e=1', encoding="utf-8")
        self.run_script("build_chat_dict.py", paths={"EXTRACTED_DIR": ROOT / "data/extracted"})
        self.run_script("patch_app.py", "chat")
        for rel, f in paths.items():
            text = f.read_text(encoding="utf-8")
            inst = "RL" if "sessions" in rel else "Uo"
            self.assertIn(f'{inst}.addResourceBundle("en","review",JSON.parse(', text)
            self.assertIn('"keepMe":"ORIG"', text)  # original overrides preserved by merge
            self.assertIn('"每日配额用量"', text)
            self.assertIn('label:"关"', text)
            self.assertIn('category:"Off"', text)
            self.assertIn('x="Off"', text)
            self.assertIn('id:"Off"', text)
            self.assertIn('labelKey:"Off"', text)
            self.assertIn('y==="Off"', text)
            self.assertIn('{"Off":1}', text)
            self.assertTrue(text.endswith('"Off"/*devin-zh*/'))  # outside region untouched
            self.assertNotIn("/*devin-zh*/", (f.parent / (f.name + ".devin-zh.bak")).read_text(encoding="utf-8"))
        wb_text = wb.read_text(encoding="utf-8")
        self.assertIn('label:"开"', wb_text)
        self.assertIn('category:"User Interface"', wb_text)
        self.assertTrue(wb_text.startswith('q="On";'))
        before = {f: f.read_bytes() for f in (*paths.values(), wb)}
        self.run_script("patch_app.py", "chat")
        self.assertEqual(before, {f: f.read_bytes() for f in before})

    def test_product_json_checksums_updated(self):
        import base64
        import hashlib

        def digest(b):
            return base64.b64encode(hashlib.sha256(b).digest()).decode().rstrip("=")

        chat = self.app / "out/vs/workbench/windsurf-chat-client/index.js"
        chat.parent.mkdir(parents=True, exist_ok=True)
        chat.write_text(self._make_chat_bundle(
            't&&Uo.addResourceBundle("en","translation",t,!0,!0),Uo}'), encoding="utf-8")
        untouched = self.app / "out/vs/workbench/other.js"
        untouched.write_text("plain", encoding="utf-8")
        product = (
            '{\n\t"nameShort": "Devin",\n\t"checksums": {\n'
            '\t\t"vs/workbench/windsurf-chat-client/index.js": "' + digest(chat.read_bytes()) + '",\n'
            '\t\t"vs/workbench/other.js": "' + digest(untouched.read_bytes()) + '"\n\t},\n\t"zig": 1\n}')
        pj = self.app / "product.json"
        pj.write_text(product, encoding="utf-8")
        self.run_script("build_chat_dict.py", paths={"EXTRACTED_DIR": ROOT / "data/extracted"})
        self.run_script("patch_app.py", "chat")
        new_text = pj.read_text(encoding="utf-8")
        data = json.loads(new_text)
        self.assertEqual(data["checksums"]["vs/workbench/windsurf-chat-client/index.js"],
                         digest(chat.read_bytes()))
        self.assertEqual(data["checksums"]["vs/workbench/other.js"],
                         digest(untouched.read_bytes()))
        self.assertEqual(data["nameShort"], "Devin")
        self.assertEqual(data["zig"], 1)
        # only the hash value differs from the original text
        import re
        stripped = re.sub(r'"[A-Za-z0-9+/]{40,}"', '"X"', product)
        stripped_new = re.sub(r'"[A-Za-z0-9+/]{40,}"', '"X"', new_text)
        self.assertEqual(stripped, stripped_new)
        self.assertEqual(pj.with_name("product.json.devin-zh.bak").read_text(encoding="utf-8"),
                         product)
        self.run_script("patch_app.py", "chat")
        self.assertEqual(pj.read_text(encoding="utf-8"), new_text)

    def test_bundle_patch_reapplies_updated_translations(self):
        import shutil
        tr_dir = self.work / "translations"
        shutil.copytree(TRANSLATIONS, tr_dir)
        chat = self.app / "out/vs/workbench/windsurf-chat-client/index.js"
        chat.parent.mkdir(parents=True, exist_ok=True)
        chat.write_text(self._make_chat_bundle(
            't&&Uo.addResourceBundle("en","translation",t,!0,!0),Uo}'), encoding="utf-8")
        self.run_script("build_chat_dict.py",
                        paths={"TRANSLATIONS_DIR": tr_dir, "EXTRACTED_DIR": ROOT / "data/extracted"})
        self.run_script("patch_app.py", "chat", paths={"TRANSLATIONS_DIR": tr_dir})
        self.assertIn('label:"关"', chat.read_text(encoding="utf-8"))
        ui = tr_dir / "app/ui_patch.json"
        ui.write_text(ui.read_text(encoding="utf-8").replace('"Off": "关"', '"Off": "XX"'),
                      encoding="utf-8")
        self.run_script("patch_app.py", "chat", paths={"TRANSLATIONS_DIR": tr_dir})
        text = chat.read_text(encoding="utf-8")
        self.assertIn('label:"XX"', text)
        self.assertIn('"keepMe":"ORIG"', text)
        self.assertNotIn("/*devin-zh*/",
                         chat.with_name(chat.name + ".devin-zh.bak").read_text(encoding="utf-8"))

    def test_legacy_install_reads_relocated_translations(self):
        self.run_script("install.py")
        main = load(self.pack / "translations/main.i18n.json")
        self.assertEqual(main["contents"], load(TRANSLATIONS / "core/zh_patch.json"))
        self.assertTrue((self.pack / "translations/main.i18n.json.devin-zh.bak").is_file())


if __name__ == "__main__":
    unittest.main()
