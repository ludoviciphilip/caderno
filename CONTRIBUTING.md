# Contributing to Caderno

Thanks for your interest in Caderno! It's a small, personal project, but issues and pull requests are welcome.

## Set up a dev environment

Requirements: GTK 4, libadwaita 1.4+ and PyGObject (system packages), plus `pycairo`.

```bash
sudo pacman -S gtk4 libadwaita python-gobject   # or the equivalent on your distro
git clone https://github.com/ludoviciphilip/caderno.git
cd caderno
./instalar.sh        # installs a venv + the `caderno` command for your user
caderno               # run it
```

If `python-cairo` is already installed system-wide, you can skip the installer and run the app directly from the
source tree:

```bash
python -m caderno
```

Set `CADERNO_DIR=/tmp/caderno-dev` while developing so you don't write test notebooks into your real
`~/Documents/Cadernos`. `CADERNO_LANG=en|pt|es` forces the UI language for a single run.

## Project layout

- `caderno/` — the application: `app.py` (entry point), `home.py` (home screen), `editor.py` (notebook/editor,
  pen input, shapes, headings), `render.py` (Cairo drawing + PDF export), `store.py` (on-disk notebook format),
  `i18n.py` (translations), `settings.py`, `toolbar.py`, `model.py`, `shapes.py`.
- `data/` — app icon.
- `docs/` — screenshots used in the README.

There is currently no automated test suite; please test changes manually with a real or virtual pen input and
describe what you tested in your pull request.

## Making a change

1. Fork the repo and create a branch from `main`.
2. Keep changes focused; unrelated reformatting makes review harder.
3. If you touch UI strings, update all three languages in `caderno/i18n.py` (or leave a note if you can't translate
   one of them).
4. Open a pull request describing the change and how you tested it (ideally with a screenshot or short clip for
   UI changes).

## Reporting bugs

Please use the bug report issue template and include your distro, GTK/libadwaita versions, and tablet model if the
issue is pen/pressure related.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — please don't open a public issue for security problems.
