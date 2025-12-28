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
            except Exception:
                pass
            self.iface.removeDockWidget(self._swipe_dock)
            self._swipe_dock.deleteLater()
            self._swipe_dock = None

        if self._settings_dock:
            self.iface.removeDockWidget(self._settings_dock)
            self._settings_dock.deleteLater()
            self._settings_dock = None

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
                    Qt.RightDockWidgetArea, self._transparency_dock
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
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self._swipe_dock)
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
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self._settings_dock)
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
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to open update checker:\n{str(e)}",
            )
