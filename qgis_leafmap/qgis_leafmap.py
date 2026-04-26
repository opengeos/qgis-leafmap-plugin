"""
Leafmap QGIS Plugin - Main Plugin Class

This module contains the main plugin class that manages the QGIS interface
integration, menu items, toolbar buttons, and dockable panels for layer
transparency control and swipe comparison tools.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox


class QgisLeafmap:
    """QgisLeafmap implementation class for QGIS."""

    def __init__(self, iface):
        """Constructor.

        Args:
            iface: An interface instance that provides the hook to QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = None
        self.toolbar = None

        # Dock widgets (lazy loaded)
        self._transparency_dock = None
        self._swipe_dock = None
        self._settings_dock = None
        self._code_editor_dock = None
        self._coordinates_dock = None
        self._export_dock = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        checkable=False,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        Args:
            icon_path: Path to the icon for this action.
            text: Text that appears in the menu for this action.
            callback: Function to be called when the action is triggered.
            enabled_flag: A flag indicating if the action should be enabled.
            add_to_menu: Flag indicating whether action should be added to menu.
            add_to_toolbar: Flag indicating whether action should be added to toolbar.
            status_tip: Optional text to show in status bar when mouse hovers over action.
            checkable: Whether the action is checkable (toggle).
            parent: Parent widget for the new action.

        Returns:
            The action that was created.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.menu.addAction(action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create menu
        self.menu = QMenu("&Leafmap")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # Create toolbar
        self.toolbar = QToolBar("Leafmap Toolbar")
        self.toolbar.setObjectName("LeafmapToolbar")
        self.iface.addToolBar(self.toolbar)

        # Get icon paths
        icon_base = os.path.join(self.plugin_dir, "icons")

        # Transparency panel icon
        transparency_icon = os.path.join(icon_base, "transparency.svg")
        if not os.path.exists(transparency_icon):
            transparency_icon = ":/images/themes/default/mIconRasterLayer.svg"

        # Swipe panel icon
        swipe_icon = os.path.join(icon_base, "swipe.svg")
        if not os.path.exists(swipe_icon):
            swipe_icon = ":/images/themes/default/mActionSplitFeatures.svg"

        # Settings icon
        settings_icon = os.path.join(icon_base, "settings.svg")
        if not os.path.exists(settings_icon):
            settings_icon = ":/images/themes/default/mActionOptions.svg"

        # About icon
        about_icon = os.path.join(icon_base, "about.svg")
        if not os.path.exists(about_icon):
            about_icon = ":/images/themes/default/mActionHelpContents.svg"

        # Code Editor icon
        code_editor_icon = os.path.join(icon_base, "code_editor.svg")
        if not os.path.exists(code_editor_icon):
            code_editor_icon = ":/images/themes/default/mIconPythonFile.svg"

        # Add Transparency Panel action (checkable for dock toggle)
        self.transparency_action = self.add_action(
            transparency_icon,
            "Layer Transparency",
            self.toggle_transparency_dock,
            status_tip="Toggle Layer Transparency Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add Swipe Panel action (checkable for dock toggle)
        self.swipe_action = self.add_action(
            swipe_icon,
            "Layer Swipe",
            self.toggle_swipe_dock,
            status_tip="Toggle Layer Swipe Panel for comparing layers",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add Python Editor action (checkable for dock toggle)
        self.code_editor_action = self.add_action(
            code_editor_icon,
            "Python Editor",
            self.toggle_code_editor_dock,
            status_tip="Toggle Python Code Editor",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Coordinates icon
        coordinates_icon = os.path.join(icon_base, "coordinates.svg")
        if not os.path.exists(coordinates_icon):
            coordinates_icon = ":/images/themes/default/mActionMapTips.svg"

        # Export icon
        export_icon = os.path.join(icon_base, "export.svg")
        if not os.path.exists(export_icon):
            export_icon = ":/images/themes/default/mActionFileSaveAs.svg"

        # Add Coordinate Retrieval action (checkable for dock toggle)
        self.coordinates_action = self.add_action(
            coordinates_icon,
            "Coordinate Retrieval",
            self.toggle_coordinates_dock,
            status_tip="Toggle Coordinate Retrieval Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add Export Layer action (checkable for dock toggle)
        self.export_action = self.add_action(
            export_icon,
            "Export Layer",
            self.toggle_export_dock,
            status_tip="Toggle Export Layer Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add Settings Panel action (checkable for dock toggle)
        self.settings_action = self.add_action(
            settings_icon,
            "Settings",
            self.toggle_settings_dock,
            status_tip="Toggle Settings Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add separator to menu
        self.menu.addSeparator()

        # Update icon - use QGIS default download/update icon
        update_icon = ":/images/themes/default/mActionRefresh.svg"

        # Add Check for Updates action (menu only)
        self.add_action(
            update_icon,
            "Check for Updates...",
            self.show_update_checker,
            add_to_toolbar=False,
            status_tip="Check for plugin updates from GitHub",
            parent=self.iface.mainWindow(),
        )

        # Add About action (menu only)
        self.add_action(
            about_icon,
            "About Leafmap",
            self.show_about,
            add_to_toolbar=False,
            status_tip="About Leafmap QGIS Plugin",
            parent=self.iface.mainWindow(),
        )

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        # Remove dock widgets
        if self._transparency_dock:
            self.iface.removeDockWidget(self._transparency_dock)
            self._transparency_dock.deleteLater()
            self._transparency_dock = None

        if self._swipe_dock:
            # Make sure to clean up the swipe tool
            try:
                self._swipe_dock.cleanup()
            except Exception:  # nosec B110
                # Best-effort cleanup during plugin unload; we still want to
                # remove the dock even if its internal cleanup raises.
                pass
            self.iface.removeDockWidget(self._swipe_dock)
            self._swipe_dock.deleteLater()
            self._swipe_dock = None

        if self._settings_dock:
            self.iface.removeDockWidget(self._settings_dock)
            self._settings_dock.deleteLater()
            self._settings_dock = None

        if self._code_editor_dock:
            self.iface.removeDockWidget(self._code_editor_dock)
            self._code_editor_dock.deleteLater()
            self._code_editor_dock = None

        if self._coordinates_dock:
            try:
                self._coordinates_dock.cleanup()
            except Exception:  # nosec B110
                # Best-effort cleanup during plugin unload.
                pass
            self.iface.removeDockWidget(self._coordinates_dock)
            self._coordinates_dock.deleteLater()
            self._coordinates_dock = None

        if self._export_dock:
            try:
                self._export_dock.cleanup()
            except Exception:  # nosec B110
                # Best-effort cleanup during plugin unload.
                pass
            self.iface.removeDockWidget(self._export_dock)
            self._export_dock.deleteLater()
            self._export_dock = None

        # Remove actions from menu
        for action in self.actions:
            self.iface.removePluginMenu("&Leafmap", action)

        # Remove toolbar
        if self.toolbar:
            del self.toolbar

        # Remove menu
        if self.menu:
            self.menu.deleteLater()

    def toggle_transparency_dock(self):
        """Toggle the Layer Transparency dock widget visibility."""
        if self._transparency_dock is None:
            try:
                from .dialogs.transparency_dock import TransparencyDockWidget

                self._transparency_dock = TransparencyDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._transparency_dock.setObjectName("LeafmapTransparencyDock")
                self._transparency_dock.visibilityChanged.connect(
                    self._on_transparency_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._transparency_dock
                )
                self._transparency_dock.show()
                self._transparency_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Transparency panel:\n{str(e)}",
                )
                self.transparency_action.setChecked(False)
                return

        # Toggle visibility
        if self._transparency_dock.isVisible():
            self._transparency_dock.hide()
        else:
            self._transparency_dock.show()
            self._transparency_dock.raise_()

    def _on_transparency_visibility_changed(self, visible):
        """Handle Transparency dock visibility change."""
        self.transparency_action.setChecked(visible)

    def toggle_swipe_dock(self):
        """Toggle the Layer Swipe dock widget visibility."""
        if self._swipe_dock is None:
            try:
                from .dialogs.swipe_dock import SwipeDockWidget

                self._swipe_dock = SwipeDockWidget(self.iface, self.iface.mainWindow())
                self._swipe_dock.setObjectName("LeafmapSwipeDock")
                self._swipe_dock.visibilityChanged.connect(
                    self._on_swipe_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._swipe_dock
                )
                self._swipe_dock.show()
                self._swipe_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Swipe panel:\n{str(e)}",
                )
                self.swipe_action.setChecked(False)
                return

        # Toggle visibility
        if self._swipe_dock.isVisible():
            self._swipe_dock.hide()
        else:
            self._swipe_dock.show()
            self._swipe_dock.raise_()

    def _on_swipe_visibility_changed(self, visible):
        """Handle Swipe dock visibility change."""
        self.swipe_action.setChecked(visible)

    def toggle_settings_dock(self):
        """Toggle the Settings dock widget visibility."""
        if self._settings_dock is None:
            try:
                from .dialogs.settings_dock import SettingsDockWidget

                self._settings_dock = SettingsDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._settings_dock.setObjectName("LeafmapSettingsDock")
                self._settings_dock.visibilityChanged.connect(
                    self._on_settings_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._settings_dock
                )
                self._settings_dock.show()
                self._settings_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Settings panel:\n{str(e)}",
                )
                self.settings_action.setChecked(False)
                return

        # Toggle visibility
        if self._settings_dock.isVisible():
            self._settings_dock.hide()
        else:
            self._settings_dock.show()
            self._settings_dock.raise_()

    def _on_settings_visibility_changed(self, visible):
        """Handle Settings dock visibility change."""
        self.settings_action.setChecked(visible)

    def toggle_code_editor_dock(self):
        """Toggle the Python Editor dock widget visibility."""
        if self._code_editor_dock is None:
            try:
                from .dialogs.code_editor_dock import CodeEditorDockWidget

                self._code_editor_dock = CodeEditorDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._code_editor_dock.setObjectName("LeafmapCodeEditorDock")
                self._code_editor_dock.visibilityChanged.connect(
                    self._on_code_editor_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._code_editor_dock
                )
                self._code_editor_dock.show()
                self._code_editor_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Code Editor panel:\n{str(e)}",
                )
                self.code_editor_action.setChecked(False)
                return

        # Toggle visibility
        if self._code_editor_dock.isVisible():
            self._code_editor_dock.hide()
        else:
            self._code_editor_dock.show()
            self._code_editor_dock.raise_()

    def _on_code_editor_visibility_changed(self, visible):
        """Handle Code Editor dock visibility change."""
        self.code_editor_action.setChecked(visible)

    def toggle_coordinates_dock(self):
        """Toggle the Coordinate Retrieval dock widget visibility."""
        if self._coordinates_dock is None:
            try:
                from .dialogs.coordinates_dock import CoordinatesDockWidget

                self._coordinates_dock = CoordinatesDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._coordinates_dock.setObjectName("LeafmapCoordinatesDock")
                self._coordinates_dock.visibilityChanged.connect(
                    self._on_coordinates_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._coordinates_dock
                )
                self._coordinates_dock.show()
                self._coordinates_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Coordinate Retrieval panel:\n{str(e)}",
                )
                self.coordinates_action.setChecked(False)
                return

        # Toggle visibility
        if self._coordinates_dock.isVisible():
            self._coordinates_dock.hide()
        else:
            self._coordinates_dock.show()
            self._coordinates_dock.raise_()

    def _on_coordinates_visibility_changed(self, visible):
        """Handle Coordinates dock visibility change."""
        self.coordinates_action.setChecked(visible)

    def toggle_export_dock(self):
        """Toggle the Export Layer dock widget visibility."""
        if self._export_dock is None:
            try:
                from .dialogs.export_dock import ExportDockWidget

                self._export_dock = ExportDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._export_dock.setObjectName("LeafmapExportDock")
                self._export_dock.visibilityChanged.connect(
                    self._on_export_visibility_changed
                )
                self.iface.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, self._export_dock
                )
                self._export_dock.show()
                self._export_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Export Layer panel:\n{str(e)}",
                )
                self.export_action.setChecked(False)
                return

        if self._export_dock.isVisible():
            self._export_dock.hide()
        else:
            self._export_dock.show()
            self._export_dock.raise_()

    def _on_export_visibility_changed(self, visible):
        """Handle Export dock visibility change."""
        self.export_action.setChecked(visible)

    def show_about(self):
        """Display the about dialog."""
        # Read version from metadata.txt
        version = "Unknown"
        try:
            metadata_path = os.path.join(self.plugin_dir, "metadata.txt")
            with open(metadata_path, "r", encoding="utf-8") as f:
                import re

                content = f.read()
                version_match = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if version_match:
                    version = version_match.group(1).strip()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Leafmap",
                f"Could not read version from metadata.txt:\n{str(e)}",
            )

        about_text = f"""
<h2>Leafmap for QGIS</h2>
<p>Version: {version}</p>
<p>Author: Qiusheng Wu</p>

<h3>Features:</h3>
<ul>
<li><b>Layer Transparency:</b> Interactive slider to control layer transparency in real-time</li>
<li><b>Layer Swipe:</b> Compare two layers side-by-side with a draggable divider (similar to ipyleaflet split control)</li>
<li><b>Settings Panel:</b> Configure plugin options</li>
<li><b>Update Checker:</b> Check for plugin updates from GitHub</li>
</ul>

<h3>Links:</h3>
<ul>
<li><a href="https://github.com/opengeos/qgis-leafmap-plugin">GitHub Repository</a></li>
<li><a href="https://github.com/opengeos/qgis-leafmap-plugin/issues">Report Issues</a></li>
<li><a href="https://leafmap.org">Leafmap Documentation</a></li>
</ul>

<p>Licensed under MIT License</p>
<p>Inspired by the <a href="https://github.com/opengeos/leafmap">leafmap</a> Python package</p>
"""
        QMessageBox.about(
            self.iface.mainWindow(),
            "About Leafmap",
            about_text,
        )

    def show_update_checker(self):
        """Display the update checker dialog."""
        try:
            from .dialogs.update_checker import UpdateCheckerDialog
        except ImportError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to import update checker dialog:\n{str(e)}",
            )
            return

        try:
            dialog = UpdateCheckerDialog(self.plugin_dir, self.iface.mainWindow())
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to open update checker:\n{str(e)}",
            )
