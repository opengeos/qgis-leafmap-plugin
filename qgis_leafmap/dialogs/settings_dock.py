"""
Settings Dock Widget for Leafmap Plugin

This module provides a settings panel for configuring
the Leafmap plugin options.
"""

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QFormLayout,
    QMessageBox,
    QTabWidget,
)
from qgis.PyQt.QtGui import QFont


class SettingsDockWidget(QDockWidget):
    """A settings panel for configuring Leafmap plugin options."""

    # Settings keys
    SETTINGS_PREFIX = "Leafmap/"

    def __init__(self, iface, parent=None):
        """Initialize the settings dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Leafmap Settings", parent)
        self.iface = iface
        self.settings = QSettings()

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Set up the settings UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Main layout
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)

        # Header
        header_label = QLabel("Leafmap Settings")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Tab widget for organized settings
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # General settings tab
        general_tab = self._create_general_tab()
        tab_widget.addTab(general_tab, "General")

        # Transparency settings tab
        transparency_tab = self._create_transparency_tab()
        tab_widget.addTab(transparency_tab, "Transparency")

        # Swipe settings tab
        swipe_tab = self._create_swipe_tab()
        tab_widget.addTab(swipe_tab, "Swipe")

        # Buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(self.reset_btn)

        layout.addLayout(button_layout)

        # Stretch at the end
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Settings loaded")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _create_general_tab(self):
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # General options group
        general_group = QGroupBox("General Options")
        general_layout = QFormLayout(general_group)

        # Show notifications
        self.notifications_check = QCheckBox()
        self.notifications_check.setChecked(True)
        general_layout.addRow("Show notifications:", self.notifications_check)

        # Auto-check for updates
        self.auto_update_check = QCheckBox()
        self.auto_update_check.setChecked(True)
        general_layout.addRow("Auto-check for updates:", self.auto_update_check)

        # Remember dock positions
        self.remember_docks_check = QCheckBox()
        self.remember_docks_check.setChecked(True)
        general_layout.addRow("Remember dock positions:", self.remember_docks_check)

        layout.addWidget(general_group)

        # Display group
        display_group = QGroupBox("Display Options")
        display_layout = QFormLayout(display_group)

        # Default dock position
        self.dock_position_combo = QComboBox()
        self.dock_position_combo.addItems(["Right", "Left"])
        display_layout.addRow("Default dock position:", self.dock_position_combo)

        layout.addWidget(display_group)

        layout.addStretch()
        return widget

    def _create_transparency_tab(self):
        """Create the transparency settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Transparency group
        trans_group = QGroupBox("Transparency Panel")
        trans_layout = QFormLayout(trans_group)

        # Default filter type
        self.trans_filter_combo = QComboBox()
        self.trans_filter_combo.addItems(
            ["All Layers", "Raster Layers", "Vector Layers"]
        )
        trans_layout.addRow("Default layer filter:", self.trans_filter_combo)

        # Show visible only by default
        self.trans_visible_only_check = QCheckBox()
        self.trans_visible_only_check.setChecked(False)
        trans_layout.addRow("Show visible only:", self.trans_visible_only_check)

        # Default transparency step
        self.trans_step_spin = QSpinBox()
        self.trans_step_spin.setRange(1, 25)
        self.trans_step_spin.setValue(5)
        self.trans_step_spin.setSuffix("%")
        trans_layout.addRow("Slider step:", self.trans_step_spin)

        layout.addWidget(trans_group)

        layout.addStretch()
        return widget

    def _create_swipe_tab(self):
        """Create the swipe tool settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Swipe group
        swipe_group = QGroupBox("Swipe Tool")
        swipe_layout = QFormLayout(swipe_group)

        # Default orientation
        self.swipe_orientation_combo = QComboBox()
        self.swipe_orientation_combo.addItems(["Vertical", "Horizontal"])
        swipe_layout.addRow("Default orientation:", self.swipe_orientation_combo)

        # Default position
        self.swipe_position_spin = QSpinBox()
        self.swipe_position_spin.setRange(0, 100)
        self.swipe_position_spin.setValue(50)
        self.swipe_position_spin.setSuffix("%")
        swipe_layout.addRow("Default position:", self.swipe_position_spin)

        # Divider width
        self.swipe_divider_spin = QSpinBox()
        self.swipe_divider_spin.setRange(2, 10)
        self.swipe_divider_spin.setValue(4)
        self.swipe_divider_spin.setSuffix(" px")
        swipe_layout.addRow("Divider width:", self.swipe_divider_spin)

        # Show divider handle
        self.swipe_show_handle_check = QCheckBox()
        self.swipe_show_handle_check.setChecked(True)
        swipe_layout.addRow("Show drag handle:", self.swipe_show_handle_check)

        layout.addWidget(swipe_group)

        layout.addStretch()
        return widget

    def _load_settings(self):
        """Load settings from QSettings."""
        # General
        self.notifications_check.setChecked(
            self.settings.value(f"{self.SETTINGS_PREFIX}notifications", True, type=bool)
        )
        self.auto_update_check.setChecked(
            self.settings.value(f"{self.SETTINGS_PREFIX}auto_update", True, type=bool)
        )
        self.remember_docks_check.setChecked(
            self.settings.value(
                f"{self.SETTINGS_PREFIX}remember_docks", True, type=bool
            )
        )
        self.dock_position_combo.setCurrentIndex(
            self.settings.value(f"{self.SETTINGS_PREFIX}dock_position", 0, type=int)
        )

        # Transparency
        self.trans_filter_combo.setCurrentIndex(
            self.settings.value(f"{self.SETTINGS_PREFIX}trans_filter", 0, type=int)
        )
        self.trans_visible_only_check.setChecked(
            self.settings.value(
                f"{self.SETTINGS_PREFIX}trans_visible_only", False, type=bool
            )
        )
        self.trans_step_spin.setValue(
            self.settings.value(f"{self.SETTINGS_PREFIX}trans_step", 5, type=int)
        )

        # Swipe
        self.swipe_orientation_combo.setCurrentIndex(
            self.settings.value(f"{self.SETTINGS_PREFIX}swipe_orientation", 0, type=int)
        )
        self.swipe_position_spin.setValue(
            self.settings.value(f"{self.SETTINGS_PREFIX}swipe_position", 50, type=int)
        )
        self.swipe_divider_spin.setValue(
            self.settings.value(f"{self.SETTINGS_PREFIX}swipe_divider", 4, type=int)
        )
        self.swipe_show_handle_check.setChecked(
            self.settings.value(
                f"{self.SETTINGS_PREFIX}swipe_show_handle", True, type=bool
            )
        )

        self.status_label.setText("Settings loaded")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def _save_settings(self):
        """Save settings to QSettings."""
        # General
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}notifications", self.notifications_check.isChecked()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}auto_update", self.auto_update_check.isChecked()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}remember_docks",
            self.remember_docks_check.isChecked(),
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}dock_position",
            self.dock_position_combo.currentIndex(),
        )

        # Transparency
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}trans_filter",
            self.trans_filter_combo.currentIndex(),
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}trans_visible_only",
            self.trans_visible_only_check.isChecked(),
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}trans_step", self.trans_step_spin.value()
        )

        # Swipe
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}swipe_orientation",
            self.swipe_orientation_combo.currentIndex(),
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}swipe_position", self.swipe_position_spin.value()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}swipe_divider", self.swipe_divider_spin.value()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}swipe_show_handle",
            self.swipe_show_handle_check.isChecked(),
        )

        self.settings.sync()

        self.status_label.setText("Settings saved")
        self.status_label.setStyleSheet("color: green; font-size: 10px;")

        self.iface.messageBar().pushSuccess("Leafmap", "Settings saved successfully!")

    def _reset_defaults(self):
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # General
        self.notifications_check.setChecked(True)
        self.auto_update_check.setChecked(True)
        self.remember_docks_check.setChecked(True)
        self.dock_position_combo.setCurrentIndex(0)

        # Transparency
        self.trans_filter_combo.setCurrentIndex(0)
        self.trans_visible_only_check.setChecked(False)
        self.trans_step_spin.setValue(5)

        # Swipe
        self.swipe_orientation_combo.setCurrentIndex(0)
        self.swipe_position_spin.setValue(50)
        self.swipe_divider_spin.setValue(4)
        self.swipe_show_handle_check.setChecked(True)

        self.status_label.setText("Defaults restored (not saved)")
        self.status_label.setStyleSheet("color: orange; font-size: 10px;")
