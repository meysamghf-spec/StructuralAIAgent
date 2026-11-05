"""Fonts for ezdxf PDF/PNG rendering.

The backend image has no system fonts (no /usr/share/fonts). ezdxf then falls back to its MonospaceFont, which draws
every TEXT/MTEXT as an empty rectangle: the structural-set PDF looked blank (2026-11-04). matplotlib ships DejaVu
(Latin + Arabic/Persian glyphs), so we register its folder with the ezdxf font manager once.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_ready = False


def _candidate_folders() -> list[str]:
    folders: list[str] = []
    extra = os.environ.get("SAIA_FONT_DIRS", "")
    folders += [f for f in extra.split(os.pathsep) if f]
    try:
        import matplotlib

        folders.append(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"))
    except Exception:  # noqa: BLE001
        pass
    folders += ["/usr/share/fonts", "/usr/local/share/fonts"]
    return [f for f in folders if os.path.isdir(f)]


def fonts_available() -> bool:
    from ezdxf.fonts import fonts

    try:
        return type(fonts.make_font("DejaVuSans.ttf", 1.0)).__name__ != "MonospaceFont"
    except Exception:  # noqa: BLE001
        return False


def ensure_fonts() -> bool:
    """Make real TTF fonts available to ezdxf. Returns False if text would still render as boxes."""
    global _ready
    if _ready:
        return True
    with _lock:
        if _ready:
            return True
        if not fonts_available():
            from ezdxf.fonts import fonts

            folders = _candidate_folders()
            try:
                fonts.font_manager.build(folders=folders, support_dirs=True)
                fonts.font_manager._match_cache.clear()  # noqa: SLF001 - drop cached 'no font' matches
            except Exception:  # noqa: BLE001
                logger.exception("ezdxf font registration failed (%s)", folders)
        _ready = fonts_available()
        if not _ready:
            logger.error("no TTF fonts for ezdxf; PDF text would render as empty boxes")
        return _ready


def require_fonts() -> None:
    if not ensure_fonts():
        raise ValueError("no fonts available on the server to render drawing text / فونتی برای نوشتن متن نقشه روی سرور نیست")
