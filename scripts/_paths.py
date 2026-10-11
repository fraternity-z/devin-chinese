import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = ROOT / "translations"
EXTRACTED_DIR = ROOT / "data" / "extracted"
REPORTS_DIR = ROOT / "data" / "reports"
CHAT_BUILD_DIR = ROOT / "build" / "chat"
DIST_DIR = ROOT / "dist"

DEVIN_APP = Path(os.environ.get("DEVIN_APP", r"E:\Devin\resources\app")).expanduser().resolve()
PACK_DIR = Path(os.environ.get(
    "VSCODE_ZH_PACK",
    Path.home() / ".devin" / "extensions" / "ms-ceintl.vscode-language-pack-zh-hans-1.126.0-universal",
)).expanduser().resolve()
