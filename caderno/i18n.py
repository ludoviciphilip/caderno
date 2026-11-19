"""Tradução da interface: português (original), inglês e espanhol.

`_("texto em português")` devolve o texto no idioma escolhido. O idioma vem de
~/.config/caderno/config.json ("lang": "auto" | "pt" | "en" | "es"); em "auto",
do idioma do sistema (pt e es pelo prefixo; o resto cai no inglês).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "caderno" / "config.json"
LANGUAGES = {"auto": None, "pt": "Português", "en": "English", "es": "Español"}

# português -> (inglês, espanhol)
CATALOG = {
    # início
    "Cadernos": ("Notebooks", "Cuadernos"),
    "Pesquisar": ("Search", "Buscar"),
    "Novo caderno": ("New notebook", "Nuevo cuaderno"),
    "Nova pasta": ("New folder", "Nueva carpeta"),
    "Criar": ("Create", "Crear"),
    "Cancelar": ("Cancel", "Cancelar"),
    "Renomear": ("Rename", "Renombrar"),
    "Renomear…": ("Rename…", "Renombrar…"),
    "Mover": ("Move", "Mover"),
    "Mover para…": ("Move to…", "Mover a…"),
    "Mover “{name}” para…": ("Move “{name}” to…", "Mover «{name}» a…"),
    "Mover para a lixeira": ("Move to trash", "Mover a la papelera"),
    "Mover “{name}” para a lixeira?": ("Move “{name}” to the trash?", "¿Mover «{name}» a la papelera?"),
    "Dá para recuperar pela lixeira do sistema.": ("You can restore it from the system trash.",
                                                   "Se puede recuperar desde la papelera del sistema."),
    "Não consegui mover para a lixeira: {err}": ("Couldn't move to trash: {err}",
                                                 "No se pudo mover a la papelera: {err}"),
    "Cadernos (início)": ("Notebooks (home)", "Cuadernos (inicio)"),
    "Nada aqui ainda — crie um caderno ou uma pasta.": ("Nothing here yet — create a notebook or a folder.",
                                                        "Aún no hay nada — crea un cuaderno o una carpeta."),
    "Nada encontrado.": ("Nothing found.", "No se encontró nada."),
    "Idioma": ("Language", "Idioma"),
    "Automático (sistema)": ("Automatic (system)", "Automático (sistema)"),
    "Sem título": ("Untitled", "Sin título"),
    # caderno
    "Caderno": ("Notebook", "Cuaderno"),
    "Diminuir (Ctrl+-)": ("Zoom out (Ctrl+-)", "Alejar (Ctrl+-)"),
    "Aumentar (Ctrl+=)": ("Zoom in (Ctrl+=)", "Acercar (Ctrl+=)"),
    "Diminuir zoom": ("Zoom out", "Alejar"),
    "Aumentar zoom": ("Zoom in", "Acercar"),
    "Nova folha": ("New page", "Nueva hoja"),
    "Nova folha antes": ("New page before", "Nueva hoja antes"),
    "Nova folha depois": ("New page after", "Nueva hoja después"),
    "Nova folha depois desta": ("New page after this one", "Nueva hoja después de esta"),
    "Excluir folha": ("Delete page", "Eliminar hoja"),
    "Pautado": ("Ruled", "Rayado"),
    "Quadriculado": ("Grid", "Cuadriculado"),
    "Pontilhado": ("Dotted", "Punteado"),
    "Liso": ("Plain", "Liso"),
    "Imagem de um arquivo…": ("Image from a file…", "Imagen de un archivo…"),
    "Colar imagem (Ctrl+V)": ("Paste image (Ctrl+V)", "Pegar imagen (Ctrl+V)"),
    "Inserir imagem": ("Insert image", "Insertar imagen"),
    "Imagens": ("Images", "Imágenes"),
    "Exportar como PDF…": ("Export as PDF…", "Exportar como PDF…"),
    "Exportar PDF": ("Export PDF", "Exportar PDF"),
    "PDF exportado": ("PDF exported", "PDF exportado"),
    "Falha ao exportar: {err}": ("Export failed: {err}", "Error al exportar: {err}"),
    "Abrir a pasta do caderno": ("Open the notebook's folder", "Abrir la carpeta del cuaderno"),
    "Não consegui abrir a imagem: {err}": ("Couldn't open the image: {err}", "No se pudo abrir la imagen: {err}"),
    "A área de transferência não tem imagem": ("The clipboard has no image", "El portapapeles no tiene imagen"),
    "Formas inteligentes": ("Smart shapes", "Formas inteligentes"),
    "Índice": ("Index", "Índice"),
    "Índice (títulos e formas)": ("Index (headings and shapes)", "Índice (títulos y formas)"),
    "Folha {n}": ("Page {n}", "Hoja {n}"),
    "Título": ("Heading", "Título"),
    "Nenhum título ou forma ainda.\n\nPara criar um título, desenhe um # no começo da linha e segure a caneta parada.": (
        "No headings or shapes yet.\n\nTo add a heading, draw a # at the start of a line and hold the pen still.",
        "Aún no hay títulos ni formas.\n\nPara crear un título, dibuja un # al inicio de la línea y mantén el lápiz quieto."),
    "linha": ("Line", "Línea"),
    "círculo": ("Circle", "Círculo"),
    "elipse": ("Ellipse", "Elipse"),
    "retângulo": ("Rectangle", "Rectángulo"),
    "triângulo": ("Triangle", "Triángulo"),
    "Traço da caneta": ("Pen stroke", "Trazo del lápiz"),
    "Pela pressão": ("Follows pressure", "Según la presión"),
    "Pressão suave": ("Gentle pressure", "Presión suave"),
    "Uniforme": ("Uniform", "Uniforme"),
    # barra
    "Inserir": ("Insert", "Insertar"),
    "Desfazer (Ctrl+Z)": ("Undo (Ctrl+Z)", "Deshacer (Ctrl+Z)"),
    "Refazer (Ctrl+Shift+Z)": ("Redo (Ctrl+Shift+Z)", "Rehacer (Ctrl+Shift+Z)"),
    "Caneta": ("Pen", "Bolígrafo"),
    "Marca-texto": ("Highlighter", "Resaltador"),
    "Borracha": ("Eraser", "Borrador"),
    "Régua (linha reta)": ("Ruler (straight line)", "Regla (línea recta)"),
    "{tool} ({n}) — clique de novo para mudar cor e espessura": (
        "{tool} ({n}) — click again to change color and width",
        "{tool} ({n}) — haz clic de nuevo para cambiar color y grosor"),
    "Outra cor…": ("Other color…", "Otro color…"),
    "Tamanho da borracha": ("Eraser size", "Tamaño del borrador"),
}

_lang = None


def _system_lang() -> str:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v and v not in ("C", "POSIX"):
            code = v.split(":")[0][:2].lower()
            return code if code in ("pt", "es") else "en"
    return "en"


_config = None


def read_config() -> dict:
    """Lida do disco uma vez; a caneta consulta isto a cada ponto."""
    global _config
    if _config is None:
        try:
            _config = json.loads(CONFIG.read_text())
        except (OSError, ValueError):
            _config = {}
    return _config


def write_config(**changes):
    global _config
    cfg = dict(read_config())
    cfg.update(changes)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=1))
    _config = cfg


def chosen() -> str:
    """O que está na configuração: auto, pt, en ou es."""
    v = os.environ.get("CADERNO_LANG") or read_config().get("lang", "auto")
    return v if v in LANGUAGES else "auto"


def current() -> str:
    global _lang
    if _lang is None:
        c = chosen()
        _lang = _system_lang() if c == "auto" else c
    return _lang


def set_language(code: str):
    global _lang
    write_config(lang=code)
    _lang = None


def _(text: str, **fmt) -> str:
    lang = current()
    if lang != "pt" and text in CATALOG:
        text = CATALOG[text][0 if lang == "en" else 1]
    return text.format(**fmt) if fmt else text
