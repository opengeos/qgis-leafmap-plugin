"""
Leafmap Plugin Dialogs

This module contains the dialog and dock widget classes for the Leafmap plugin.
"""

from .transparency_dock import TransparencyDockWidget
from .swipe_dock import SwipeDockWidget
from .settings_dock import SettingsDockWidget
from .update_checker import UpdateCheckerDialog
from .code_editor_dock import CodeEditorDockWidget
from .coordinates_dock import CoordinatesDockWidget
from .export_dock import ExportDockWidget

__all__ = [
    "TransparencyDockWidget",
    "SwipeDockWidget",
    "SettingsDockWidget",
    "UpdateCheckerDialog",
    "CodeEditorDockWidget",
    "CoordinatesDockWidget",
    "ExportDockWidget",
]
