"""Tools to read, compare and sync Dead Cells save files across platforms.

Primary use case: bring progression from the Netflix mobile build of Dead Cells
(iPhone/iPad) into the Steam build on desktop.
"""
from .container import DCSave, DCSaveError, MAGIC_PC, MAGIC_MOBILE, FLAG_ORDER

__version__ = "1.0.0"
__all__ = ["DCSave", "DCSaveError", "MAGIC_PC", "MAGIC_MOBILE", "FLAG_ORDER"]
