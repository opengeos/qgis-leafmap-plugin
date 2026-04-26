"""
Layer Transparency Dock Widget for Leafmap Plugin

This module provides an interactive panel to control layer transparency
in real-time using sliders and spinboxes.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QGroupBox,
    QComboBox,
    QFormLayout,
    QScrollArea,
    QFrame,
    QSizePolicy,
)
from qgis.PyQt.QtGui import QFont
from qgis.core import QgsProject, QgsMapLayer, QgsRasterLayer, QgsVectorLayer


class LayerTransparencyWidget(QWidget):
    """Widget for controlling a single layer's transparency."""

    def __init__(self, layer, parent=None):
        """Initialize the layer transparency widget.

        Args:
            layer: QGIS map layer.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.layer = layer
        self._setup_ui()
        self._update_from_layer()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)

        # Layer name label
        self.name_label = QLabel(self.layer.name())
        self.name_label.setMinimumWidth(120)
        self.name_label.setMaximumWidth(200)
        self.name_label.setToolTip(self.layer.name())
        font = self.name_label.font()
        font.setPointSize(9)
        self.name_label.setFont(font)
        layout.addWidget(self.name_label)

        # Transparency slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(0)
        self.slider.setToolTip("Layer transparency (0-100%)")
        self.slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        # Spinbox for precise control
        self.spinbox = QSpinBox()
        self.spinbox.setRange(0, 100)
        self.spinbox.setValue(0)
        self.spinbox.setSuffix("%")
        self.spinbox.setToolTip("Layer transparency percentage")
        self.spinbox.setFixedWidth(60)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        layout.addWidget(self.spinbox)

    def _update_from_layer(self):
        """Update widget values from the layer's current transparency."""
        try:
            opacity = self.layer.opacity()
            transparency = int((1.0 - opacity) * 100)
            self.slider.blockSignals(True)
            self.spinbox.blockSignals(True)
            self.slider.setValue(transparency)
            self.spinbox.setValue(transparency)
            self.slider.blockSignals(False)
            self.spinbox.blockSignals(False)
        except (RuntimeError, AttributeError):
            # Layer is no longer valid
            pass

    def _on_slider_changed(self, value):
        """Handle slider value change."""
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        self._apply_transparency(value)

    def _on_spinbox_changed(self, value):
        """Handle spinbox value change."""
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._apply_transparency(value)

    def _apply_transparency(self, transparency):
        """Apply transparency to the layer.

        Args:
            transparency: Transparency percentage (0-100).
        """
        try:
            opacity = 1.0 - (transparency / 100.0)
            self.layer.setOpacity(opacity)
            self.layer.triggerRepaint()
        except (RuntimeError, AttributeError):
            # Layer is no longer valid
            pass


class TransparencyDockWidget(QDockWidget):
    """A dockable panel for controlling layer transparency."""

    def __init__(self, iface, parent=None):
        """Initialize the dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Layer Transparency", parent)
        self.iface = iface
        self.layer_widgets = {}

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._setup_ui()

        # Connect to layer changes BEFORE populating
        self._connect_project_signals()

        # Initial population
        self._populate_layers()

    def _connect_project_signals(self):
        """Connect to project signals for layer changes."""
        project = QgsProject.instance()

        # Disconnect any existing connections first
        try:
            project.layersAdded.disconnect(self._on_layers_added)
        except (RuntimeError, TypeError):
            pass

        try:
            project.layersRemoved.disconnect(self._on_layers_removed)
        except (RuntimeError, TypeError):
            pass

        try:
            project.layerTreeRoot().visibilityChanged.disconnect(
                self._on_visibility_changed
            )
        except (RuntimeError, TypeError):
            pass

        # Connect signals
        project.layersAdded.connect(self._on_layers_added)
        project.layersRemoved.connect(self._on_layers_removed)
        project.layerTreeRoot().visibilityChanged.connect(self._on_visibility_changed)

    def _setup_ui(self):
        """Set up the dock widget UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Main layout
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_label = QLabel("Layer Transparency")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            "Adjust transparency for each layer using the sliders. "
            "0% = fully opaque, 100% = fully transparent."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(desc_label)

        # Filter controls
        filter_group = QGroupBox("Filter")
        filter_layout = QFormLayout(filter_group)

        self.layer_type_combo = QComboBox()
        self.layer_type_combo.addItem("All Layers", "all")
        self.layer_type_combo.addItem("Raster Layers", "raster")
        self.layer_type_combo.addItem("Vector Layers", "vector")
        self.layer_type_combo.currentIndexChanged.connect(self._populate_layers)
        filter_layout.addRow("Layer Type:", self.layer_type_combo)

        self.visible_only_combo = QComboBox()
        self.visible_only_combo.addItem("All", False)
        self.visible_only_combo.addItem("Visible Only", True)
        self.visible_only_combo.currentIndexChanged.connect(self._populate_layers)
        filter_layout.addRow("Show:", self.visible_only_combo)

        layout.addWidget(filter_group)

        # Scroll area for layer controls
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for layer controls
        self.layers_container = QWidget()
        self.layers_layout = QVBoxLayout(self.layers_container)
        self.layers_layout.setSpacing(5)
        self.layers_layout.setContentsMargins(0, 0, 0, 0)
        self.layers_layout.addStretch()

        scroll_area.setWidget(self.layers_container)
        layout.addWidget(scroll_area, 1)  # Give scroll area the stretch

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Refresh layer list")
        self.refresh_btn.clicked.connect(self._populate_layers)
        actions_layout.addWidget(self.refresh_btn)

        self.reset_all_btn = QPushButton("Reset All")
        self.reset_all_btn.setToolTip("Reset all layers to 0% transparency")
        self.reset_all_btn.clicked.connect(self._reset_all)
        actions_layout.addWidget(self.reset_all_btn)

        self.half_all_btn = QPushButton("50% All")
        self.half_all_btn.setToolTip("Set all layers to 50% transparency")
        self.half_all_btn.clicked.connect(self._set_all_half)
        actions_layout.addWidget(self.half_all_btn)

        layout.addWidget(actions_group)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _populate_layers(self, *args):
        """Populate the layer list based on current filter settings."""
        # Clear existing widgets
        self.layer_widgets.clear()

        # Remove all widgets from layout except the stretch
        while self.layers_layout.count() > 1:
            item = self.layers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get filter settings
        layer_type = self.layer_type_combo.currentData()
        visible_only = self.visible_only_combo.currentData()

        # Get layers from project
        try:
            layers = list(QgsProject.instance().mapLayers().values())
        except (RuntimeError, AttributeError):
            layers = []

        layer_count = 0

        for layer in layers:
            # Skip invalid layers
            if layer is None:
                continue

            try:
                # Verify layer is still valid
                layer_id = layer.id()
                layer_name = layer.name()
            except (RuntimeError, AttributeError):
                # Layer is no longer valid, skip it
                continue

            # Apply type filter
            if layer_type == "raster" and not isinstance(layer, QgsRasterLayer):
                continue
            if layer_type == "vector" and not isinstance(layer, QgsVectorLayer):
                continue

            # Apply visibility filter
            if visible_only:
                try:
                    layer_tree = QgsProject.instance().layerTreeRoot()
                    tree_layer = layer_tree.findLayer(layer_id)
                    if tree_layer and not tree_layer.isVisible():
                        continue
                except (RuntimeError, AttributeError):
                    continue

            # Create widget for this layer
            try:
                widget = LayerTransparencyWidget(layer, self)
                self.layers_layout.insertWidget(layer_count, widget)
                self.layer_widgets[layer_id] = widget
                layer_count += 1
            except (RuntimeError, AttributeError):
                # Failed to create widget for this layer, skip it
                continue

        self.status_label.setText(f"{layer_count} layer(s) shown")

    def _on_layers_added(self, layers):
        """Handle new layers being added."""
        # Force immediate refresh
        self._populate_layers()
        self.update()

    def _on_layers_removed(self, layer_ids):
        """Handle layers being removed."""
        # Force immediate refresh
        self._populate_layers()
        self.update()

    def _on_visibility_changed(self, *args):
        """Handle layer visibility change."""
        if self.visible_only_combo.currentData():
            self._populate_layers()

    def _reset_all(self):
        """Reset all layers to 0% transparency."""
        for widget in self.layer_widgets.values():
            widget.slider.setValue(0)
        self.status_label.setText("All layers reset to 0%")

    def _set_all_half(self):
        """Set all layers to 50% transparency."""
        for widget in self.layer_widgets.values():
            widget.slider.setValue(50)
        self.status_label.setText("All layers set to 50%")

    def showEvent(self, event):
        """Handle dock widget show event - refresh layers when shown."""
        super().showEvent(event)
        # Reconnect signals and refresh when shown
        self._connect_project_signals()
        self._populate_layers()

    def closeEvent(self, event):
        """Handle dock widget close event."""
        # Disconnect signals
        try:
            QgsProject.instance().layersAdded.disconnect(self._on_layers_added)
            QgsProject.instance().layersRemoved.disconnect(self._on_layers_removed)
            QgsProject.instance().layerTreeRoot().visibilityChanged.disconnect(
                self._on_visibility_changed
            )
        except (RuntimeError, TypeError):
            pass

        event.accept()
