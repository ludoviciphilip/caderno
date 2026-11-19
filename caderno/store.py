"""A biblioteca no disco: pastas e cadernos dentro de ~/Documents/Cadernos."""
from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from .model import Journal, Page

FOLDER_META = ".pasta.json"
SUFFIX = ".caderno"

FOLDER_COLORS = ["#d4830a", "#43c3a6", "#4fb0e0", "#c47bdc", "#e05a6a", "#7a8a99", "#8bbf3f"]
JOURNAL_COLORS = ["#c47bdc", "#4fb0e0", "#43c3a6", "#e8a33d", "#e05a6a", "#6c7ae0", "#8bbf3f"]


def default_root() -> Path:
    import os
    if os.environ.get("CADERNO_DIR"):
        return Path(os.environ["CADERNO_DIR"]).expanduser()
    try:
        import subprocess
        docs = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True).stdout.strip()
    except OSError:
        docs = ""
    base = Path(docs) if docs and Path(docs).is_dir() else Path.home() / "Documents"
    return base / "Cadernos"


@dataclass
class Entry:
    path: Path
    kind: str      # "folder" | "journal"
    color: str

    @property
    def name(self):
        return self.path.name.removesuffix(SUFFIX)


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


def list_dir(folder: Path) -> list[Entry]:
    folder.mkdir(parents=True, exist_ok=True)
    folders, journals = [], []
    for p in folder.iterdir():
        if not p.is_dir() or p.name.startswith("."):
            continue
        if p.name.endswith(SUFFIX):
            meta = _read_json(p / "caderno.json").get("meta", {})
            journals.append(Entry(p, "journal", meta.get("color", JOURNAL_COLORS[0])))
        elif p.name != "imagens":
            folders.append(Entry(p, "folder", _read_json(p / FOLDER_META).get("color", FOLDER_COLORS[0])))
    key = lambda e: e.name.casefold()
    return sorted(folders, key=key) + sorted(journals, key=key)


def search(root: Path, text: str) -> list[Entry]:
    text = text.casefold()
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_dir() or any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        if any(part.endswith(SUFFIX) for part in p.relative_to(root).parts[:-1]):
            continue  # dentro de um caderno (imagens/)
        e = None
        if p.name.endswith(SUFFIX):
            e = Entry(p, "journal", _read_json(p / "caderno.json").get("meta", {}).get("color", JOURNAL_COLORS[0]))
        elif p.name != "imagens":
            e = Entry(p, "folder", _read_json(p / FOLDER_META).get("color", FOLDER_COLORS[0]))
        if e and text in e.name.casefold():
            out.append(e)
    return out


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = (path.name.removesuffix(SUFFIX), SUFFIX) if path.name.endswith(SUFFIX) else (path.name, "")
    n = 2
    while (path.parent / f"{stem} ({n}){suffix}").exists():
        n += 1
    return path.parent / f"{stem} ({n}){suffix}"


def _clean(name: str) -> str:
    name = name.strip().replace("/", "-")
    from .i18n import _
    return name or _("Sem título")


def create_folder(parent: Path, name: str) -> Path:
    p = _unique(parent / _clean(name))
    p.mkdir(parents=True)
    (p / FOLDER_META).write_text(json.dumps({"color": FOLDER_COLORS[0]}))
    return p


def create_journal(parent: Path, name: str) -> Path:
    p = _unique(parent / (_clean(name) + SUFFIX))
    j = Journal(p)
    j.meta["color"] = random.choice(JOURNAL_COLORS)
    j.pages = [Page()]
    j.save()
    return p


def rename(entry: Entry, new_name: str) -> Path:
    suffix = SUFFIX if entry.kind == "journal" else ""
    target = entry.path.parent / (_clean(new_name) + suffix)
    if target == entry.path:
        return target
    target = _unique(target)
    entry.path.rename(target)
    return target


def set_color(entry: Entry, color: str):
    if entry.kind == "folder":
        meta = _read_json(entry.path / FOLDER_META)
        meta["color"] = color
        (entry.path / FOLDER_META).write_text(json.dumps(meta))
    else:
        j = Journal.load(entry.path)
        j.meta["color"] = color
        j.save()


def move(entry: Entry, dest_folder: Path) -> Path:
    target = _unique(dest_folder / entry.path.name)
    shutil.move(str(entry.path), str(target))
    return target
