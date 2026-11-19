#!/usr/bin/env bash
# Instala o Caderno para o usuário (sem sudo):
#   venv em ~/.local/share/caderno/venv (com pycairo), comando ~/.local/bin/caderno,
#   atalho no menu e ícone. Rodar de novo atualiza.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
SHARE="$HOME/.local/share/caderno"
VENV="$SHARE/venv"

mkdir -p "$SHARE" "$HOME/.local/bin" "$HOME/.local/share/applications" \
         "$HOME/.local/share/icons/hicolor/scalable/apps"

if [[ ! -x "$VENV/bin/python" ]]; then
    /usr/bin/python3 -m venv --system-site-packages "$VENV"
fi
if ! "$VENV/bin/python" -c "import cairo" 2>/dev/null; then
    "$VENV/bin/pip" install -q pycairo
fi

cat > "$HOME/.local/bin/caderno" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$SRC\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$VENV/bin/python" -m caderno "\$@"
EOF
chmod +x "$HOME/.local/bin/caderno"

cp "$SRC/data/io.github.ludoviciphilip.Caderno.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"
cat > "$HOME/.local/share/applications/io.github.ludoviciphilip.Caderno.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Caderno
GenericName=Caderno digital
Comment=Anotações à mão com a mesa digitalizadora
Exec=$HOME/.local/bin/caderno
Icon=io.github.ludoviciphilip.Caderno
Terminal=false
Categories=Office;Education;
Keywords=journal;notes;notas;caderno;wacom;caneta;
StartupWMClass=io.github.ludoviciphilip.Caderno
EOF
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Caderno instalado: rode 'caderno' ou procure no menu."
