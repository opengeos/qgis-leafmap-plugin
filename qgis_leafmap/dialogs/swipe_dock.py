"""
Layer Swipe Dock Widget for Leafmap Plugin

This module provides a swipe/split tool for comparing two layers side-by-side,
similar to the ipyleaflet split control. The user can drag a divider to reveal
different portions of two layers.
"""

from qgis.PyQt.QtCore import Qt, QRectF, QObject, QEvent
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QGroupBox,
    QComboBox,
    QFormLayout,
    QRadioButton,
    QButtonGroup,
    QFrame,
)
from qgis.PyQt.QtGui import QFont, QColor, QPen, QImage, QPainter, QRegion
from qgis.core import (
    QgsProject,
    QgsMapSettings,
    QgsMapRendererCustomPainterJob,
)
from qgis.gui import QgsMapCanvasItem


class SwipeMapItem(QgsMapCanvasItem):
    """Custom map canvas item that implements the swipe effect by clipping layers."""

    def __init__(self, canvas, left_layer=None, right_layer=None):
        """Initialize the swipe map item.

        Args:
            canvas: QgsMapCanvas instance.
            left_layer: Layer to show on the left side.
            right_layer: Layer to show on the right side.
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.left_layer = left_layer
        self.right_layer = right_layer
        self.swipe_position = 0.5  # Position as fraction (0.0 to 1.0)
        self.orientation = "vertical"  # vertical or horizontal
        self.is_active = False
        self.divider_width = 4
        self.handle_size = 20

        # Store original layer opacities and visibility
        self._original_left_opacity = None
        self._original_right_opacity = None
        self._original_left_visible = None
        self._original_right_visible = None

        # Cached rendered image of right layer
        self._right_layer_image = None
        self._needs_render = True

        # Connect to canvas signals for re-rendering
        self._connected = False

    def set_left_layer(self, layer):
        """Set the left layer for comparison."""
        self.left_layer = layer
        self._needs_render = True
        if self.is_active:
            self._render_right_layer()
            self.update()

    def set_right_layer(self, layer):
        """Set the right layer for comparison."""
        self.right_layer = layer
        self._needs_render = True
        if self.is_active:
            self._render_right_layer()
            self.update()

    def set_swipe_position(self, position):
        """Set the swipe divider position.

        Args:
            position: Position as fraction (0.0 to 1.0).
        """
        self.swipe_position = max(0.0, min(1.0, position))
        self.update()

    def set_orientation(self, orientation):
        """Set the swipe orientation.

        Args:
            orientation: 'vertical' or 'horizontal'.
        """
        self.orientation = orientation
        self._needs_render = True
        if self.is_active:
            self._render_right_layer()
        self.update()

    def activate(self):
        """Activate the swipe effect."""
        if self.is_active:
            return

        self.is_active = True
        self._needs_render = True

        # Store original states
        if self.left_layer:
            try:
                self._original_left_opacity = self.left_layer.opacity()
                layer_tree_layer = (
                    QgsProject.instance()
                    .layerTreeRoot()
                    .findLayer(self.left_layer.id())
                )
                self._original_left_visible = (
                    layer_tree_layer.isVisible() if layer_tree_layer else True
                )
            except (RuntimeError, AttributeError):
                self._original_left_opacity = 1.0
                self._original_left_visible = True

        if self.right_layer:
            try:
                self._original_right_opacity = self.right_layer.opacity()
                layer_tree_layer = (
                    QgsProject.instance()
                    .layerTreeRoot()
                    .findLayer(self.right_layer.id())
                )
                self._original_right_visible = (
                    layer_tree_layer.isVisible() if layer_tree_layer else True
                )
            except (RuntimeError, AttributeError):
                self._original_right_opacity = 1.0
                self._original_right_visible = True

        # Make left layer visible and fully opaque
        self._set_layer_visible(self.left_layer, True)
        if self.left_layer:
            try:
                self.left_layer.setOpacity(1.0)
            except (RuntimeError, AttributeError):
                pass

        # Hide right layer from normal rendering - we'll render it ourselves with clipping
        self._set_layer_visible(self.right_layer, False)
        if self.right_layer:
            try:
                self.right_layer.setOpacity(1.0)
            except (RuntimeError, AttributeError):
                pass

        # Connect to canvas extent changed for re-rendering
        if not self._connected:
            self.canvas.extentsChanged.connect(self._on_extent_changed)
            self.canvas.renderComplete.connect(self._on_render_complete)
            self._connected = True

        # Initial render of right layer
        self._render_right_layer()
        self.canvas.refresh()

    def deactivate(self):
        """Deactivate the swipe effect and restore original layer states."""
        if not self.is_active:
            return

        self.is_active = False

        # Restore original opacities
        if self.left_layer and self._original_left_opacity is not None:
            try:
                self.left_layer.setOpacity(self._original_left_opacity)
            except (RuntimeError, AttributeError):
                pass

        if self.right_layer and self._original_right_opacity is not None:
            try:
                self.right_layer.setOpacity(self._original_right_opacity)
            except (RuntimeError, AttributeError):
                pass

        # Restore original visibility for right layer
        if self.right_layer and self._original_right_visible is not None:
            self._set_layer_visible(self.right_layer, self._original_right_visible)

        # Disconnect signals
        if self._connected:
            try:
                self.canvas.extentsChanged.disconnect(self._on_extent_changed)
                self.canvas.renderComplete.disconnect(self._on_render_complete)
            except (RuntimeError, TypeError):
                pass
            self._connected = False

        self._right_layer_image = None
        self.canvas.refresh()

    def _set_layer_visible(self, layer, visible):
        """Set layer visibility in layer tree."""
        if layer:
            try:
                tree_layer = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if tree_layer:
                    tree_layer.setItemVisibilityChecked(visible)
            except (RuntimeError, AttributeError):
                # Layer is invalid or removed
                pass

    def _on_extent_changed(self):
        """Handle canvas extent change."""
        self._needs_render = True
        # Render will be triggered by subsequent render_complete signal

    def _on_render_complete(self, painter):
        """Handle canvas render complete."""
        # Render right layer after canvas completes rendering
        if self.is_active and self._needs_render:
            self._render_right_layer()
            self.update()

    def _render_right_layer(self):
        """Render the right layer to an offscreen image."""
        if not self.is_active or not self.right_layer:
            self._right_layer_image = None
            return

        try:
            canvas_size = self.canvas.size()
            width = canvas_size.width()
            height = canvas_size.height()

            if width <= 0 or height <= 0:
                return

            # Create image for rendering
            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)

            # Set up map settings for rendering just the right layer
            settings = QgsMapSettings()
            settings.setOutputSize(canvas_size)
            settings.setExtent(self.canvas.extent())
            settings.setDestinationCrs(self.canvas.mapSettings().destinationCrs())
            settings.setLayers([self.right_layer])
            settings.setBackgroundColor(QColor(Qt.transparent))
            settings.setFlag(QgsMapSettings.Antialiasing, True)
            settings.setFlag(QgsMapSettings.DrawLabeling, True)

            # Render to image using QPainter with proper cleanup
            painter = QPainter()
            if painter.begin(image):
                try:
                    painter.setRenderHint(QPainter.Antialiasing, True)
                    job = QgsMapRendererCustomPainterJob(settings, painter)
                    job.start()
                    job.waitForFinished()
                finally:
                    painter.end()

                self._right_layer_image = image
                self._needs_render = False
            else:
                self._right_layer_image = None

        except Exception as e:
            print(f"Error rendering right layer: {e}")
            self._right_layer_image = None

    def paint(self, painter, option=None, widget=None):
        """Paint the swipe effect with clipped right layer and divider."""
        if not self.is_active:
            return

        try:
            canvas_size = self.canvas.size()
            width = canvas_size.width()
            height = canvas_size.height()

            if width <= 0 or height <= 0:
                return

            # Calculate divider position
            if self.orientation == "vertical":
                divider_pos = int(width * self.swipe_position)
            else:
                divider_pos = int(height * self.swipe_position)

            # Draw the right layer clipped to the right/bottom portion
            if self._right_layer_image is not None:
                painter.save()

                # Create clip region for right layer (shows on right/bottom side of divider)
                if self.orientation == "vertical":
                    clip_region = QRegion(divider_pos, 0, width - divider_pos, height)
                else:
                    clip_region = QRegion(0, divider_pos, width, height - divider_pos)

                painter.setClipRegion(clip_region)
                painter.drawImage(0, 0, self._right_layer_image)
                painter.restore()

            # Draw divider line (white with shadow)
            painter.save()

            # Shadow
            shadow_pen = QPen(QColor(0, 0, 0, 100))
            shadow_pen.setWidth(self.divider_width + 4)
            painter.setPen(shadow_pen)

            if self.orientation == "vertical":
                painter.drawLine(divider_pos, 0, divider_pos, height)
            else:
                painter.drawLine(0, divider_pos, width, divider_pos)

            # White line
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(self.divider_width)
            painter.setPen(pen)

            if self.orientation == "vertical":
                painter.drawLine(divider_pos, 0, divider_pos, height)
            else:
                painter.drawLine(0, divider_pos, width, divider_pos)

            # Draw handle
            if self.orientation == "vertical":
                hx = divider_pos - self.handle_size // 2
                hy = height // 2 - self.handle_size
                hw = self.handle_size
                hh = self.handle_size * 2
            else:
                hx = width // 2 - self.handle_size
                hy = divider_pos - self.handle_size // 2
                hw = self.handle_size * 2
                hh = self.handle_size

            # Handle background
            painter.fillRect(hx, hy, hw, hh, QColor(60, 120, 216))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(hx, hy, hw, hh)

            # Draw arrows on handle
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            cx = hx + hw // 2
            cy = hy + hh // 2

            if self.orientation == "vertical":
                # Left arrow
                painter.drawLine(cx - 5, cy, cx - 2, cy - 4)
                painter.drawLine(cx - 5, cy, cx - 2, cy + 4)
                # Right arrow
                painter.drawLine(cx + 5, cy, cx + 2, cy - 4)
                painter.drawLine(cx + 5, cy, cx + 2, cy + 4)
            else:
                # Up arrow
                painter.drawLine(cx, cy - 5, cx - 4, cy - 2)
                painter.drawLine(cx, cy - 5, cx + 4, cy - 2)
                # Down arrow
                painter.drawLine(cx, cy + 5, cx - 4, cy + 2)
                painter.drawLine(cx, cy + 5, cx + 4, cy + 2)

            painter.restore()

        except Exception as e:
            print(f"Error in SwipeMapItem.paint: {e}")

    def boundingRect(self):
        """Return the bounding rectangle for the item as QRectF."""
        try:
            canvas_size = self.canvas.size()
            return QRectF(0, 0, canvas_size.width(), canvas_size.height())
        except Exception:
            return QRectF(0, 0, 100, 100)


class SwipeMapTool(QObject):
    """Map tool for handling swipe interactions on the canvas."""

    def __init__(self, canvas, swipe_item, dock_widget, parent=None):
        """Initialize the swipe map tool.

        Args:
            canvas: QgsMapCanvas instance.
            swipe_item: SwipeMapItem instance.
            dock_widget: SwipeDockWidget for updating slider.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self.canvas = canvas
        self.swipe_item = swipe_item
        self.dock_widget = dock_widget
        self._is_dragging = False
        self._is_installed = False

    def install(self):
        """Install event filters on the canvas."""
        if not self._is_installed:
            self.canvas.viewport().installEventFilter(self)
            self._is_installed = True

    def uninstall(self):
        """Uninstall event filters from the canvas."""
        if self._is_installed:
            try:
                self.canvas.viewport().removeEventFilter(self)
            except RuntimeError:
                pass
            self._is_installed = False

    def eventFilter(self, obj, event):
        """Filter events on the canvas viewport."""
        if not self.swipe_item.is_active:
            return False

        try:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    if self._is_on_divider(event.pos()):
                        self._is_dragging = True
                        self.canvas.viewport().setCursor(
                            Qt.SplitHCursor
                            if self.swipe_item.orientation == "vertical"
                            else Qt.SplitVCursor
                        )
                        return True

            elif event.type() == QEvent.MouseMove:
                if self._is_dragging:
                    self._update_position(event.pos())
                    return True
                elif self._is_on_divider(event.pos()):
                    self.canvas.viewport().setCursor(
                        Qt.SplitHCursor
                        if self.swipe_item.orientation == "vertical"
                        else Qt.SplitVCursor
                    )
                else:
                    self.canvas.viewport().unsetCursor()

            elif event.type() == QEvent.MouseButtonRelease:
                if self._is_dragging:
                    self._is_dragging = False
                    self.canvas.viewport().unsetCursor()
                    return True

        except Exception:
            pass

        return False

    def _is_on_divider(self, pos):
        """Check if position is on the divider."""
        try:
            canvas_size = self.canvas.size()
            tolerance = 20

            if self.swipe_item.orientation == "vertical":
                divider_pos = int(canvas_size.width() * self.swipe_item.swipe_position)
                return abs(pos.x() - divider_pos) < tolerance
            else:
                divider_pos = int(canvas_size.height() * self.swipe_item.swipe_position)
                return abs(pos.y() - divider_pos) < tolerance
        except Exception:
            return False

    def _update_position(self, pos):
        """Update swipe position based on mouse position."""
        try:
            canvas_size = self.canvas.size()

            if self.swipe_item.orientation == "vertical":
                new_pos = pos.x() / canvas_size.width()
            else:
                new_pos = pos.y() / canvas_size.height()

            new_pos = max(0.0, min(1.0, new_pos))

            # Update the slider in the dock widget (which will update swipe_item)
            slider_value = int(new_pos * 100)
            self.dock_widget.position_slider.blockSignals(True)
            self.dock_widget.position_slider.setValue(slider_value)
            self.dock_widget.position_label.setText(f"{slider_value}%")
            self.dock_widget.position_slider.blockSignals(False)

            # Update position without triggering refresh
            self.swipe_item.swipe_position = new_pos
            self.swipe_item.update()

        except Exception:
            pass


class SwipeDockWidget(QDockWidget):
    """A dockable panel for layer swipe/comparison tool."""

    def __init__(self, iface, parent=None):
        """Initialize the dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Layer Swipe", parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create swipe components
        self.swipe_item = SwipeMapItem(self.canvas)
        self.swipe_tool = SwipeMapTool(self.canvas, self.swipe_item, self, self)

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
            project.layersAdded.disconnect(self._on_layers_changed)
        except (RuntimeError, TypeError):
            pass

        try:
            project.layersRemoved.disconnect(self._on_layers_changed)
        except (RuntimeError, TypeError):
            pass

        # Connect signals
        project.layersAdded.connect(self._on_layers_changed)
        project.layersRemoved.connect(self._on_layers_changed)

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
        header_label = QLabel("Layer Swipe Tool")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            "Compare two layers by swiping between them. "
            "Select left and right layers, then drag the divider on the map."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(desc_label)

        # Layer selection group
        layers_group = QGroupBox("Layer Selection")
        layers_layout = QFormLayout(layers_group)

        self.left_layer_combo = QComboBox()
        self.left_layer_combo.setToolTip("Layer shown on the left/top side")
        self.left_layer_combo.currentIndexChanged.connect(self._on_left_layer_changed)
        layers_layout.addRow("Left Layer:", self.left_layer_combo)

        self.right_layer_combo = QComboBox()
        self.right_layer_combo.setToolTip("Layer shown on the right/bottom side")
        self.right_layer_combo.currentIndexChanged.connect(self._on_right_layer_changed)
        layers_layout.addRow("Right Layer:", self.right_layer_combo)

        layout.addWidget(layers_group)

        # Orientation group
        orientation_group = QGroupBox("Swipe Direction")
        orientation_layout = QHBoxLayout(orientation_group)

        self.orientation_group = QButtonGroup(self)

        self.vertical_radio = QRadioButton("Vertical")
        self.vertical_radio.setChecked(True)
        self.vertical_radio.setToolTip("Swipe left/right")
        self.orientation_group.addButton(self.vertical_radio)
        orientation_layout.addWidget(self.vertical_radio)

        self.horizontal_radio = QRadioButton("Horizontal")
        self.horizontal_radio.setToolTip("Swipe up/down")
        self.orientation_group.addButton(self.horizontal_radio)
        orientation_layout.addWidget(self.horizontal_radio)

        self.orientation_group.buttonClicked.connect(self._on_orientation_changed)

        layout.addWidget(orientation_group)

        # Position control group
        position_group = QGroupBox("Swipe Position")
        position_layout = QVBoxLayout(position_group)

        # Slider for position
        slider_layout = QHBoxLayout()

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 100)
        self.position_slider.setValue(50)
        self.position_slider.setToolTip("Swipe divider position")
        self.position_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.position_slider)

        self.position_label = QLabel("50%")
        self.position_label.setMinimumWidth(40)
        slider_layout.addWidget(self.position_label)

        position_layout.addLayout(slider_layout)

        # Quick position buttons
        quick_btn_layout = QHBoxLayout()

        btn_0 = QPushButton("0%")
        btn_0.clicked.connect(lambda: self.position_slider.setValue(0))
        quick_btn_layout.addWidget(btn_0)

        btn_25 = QPushButton("25%")
        btn_25.clicked.connect(lambda: self.position_slider.setValue(25))
        quick_btn_layout.addWidget(btn_25)

        btn_50 = QPushButton("50%")
        btn_50.clicked.connect(lambda: self.position_slider.setValue(50))
        quick_btn_layout.addWidget(btn_50)

        btn_75 = QPushButton("75%")
        btn_75.clicked.connect(lambda: self.position_slider.setValue(75))
        quick_btn_layout.addWidget(btn_75)

        btn_100 = QPushButton("100%")
        btn_100.clicked.connect(lambda: self.position_slider.setValue(100))
        quick_btn_layout.addWidget(btn_100)

        position_layout.addLayout(quick_btn_layout)

        layout.addWidget(position_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.activate_btn = QPushButton("Activate Swipe")
        self.activate_btn.setCheckable(True)
        self.activate_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
        """
        )
        self.activate_btn.clicked.connect(self._on_activate_clicked)
        control_layout.addWidget(self.activate_btn)

        layout.addLayout(control_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Additional controls
        controls_layout2 = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Layers")
        self.refresh_btn.setToolTip("Refresh layer list")
        self.refresh_btn.clicked.connect(self._populate_layers)
        controls_layout2.addWidget(self.refresh_btn)

        self.swap_btn = QPushButton("Swap Layers")
        self.swap_btn.setToolTip("Swap left and right layers")
        self.swap_btn.clicked.connect(self._swap_layers)
        controls_layout2.addWidget(self.swap_btn)

        layout.addLayout(controls_layout2)

        # Stretch at the end
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Ready - Select layers and activate swipe")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _populate_layers(self, *args):
        """Populate the layer combo boxes."""
        current_left = self.left_layer_combo.currentData()
        current_right = self.right_layer_combo.currentData()

        self.left_layer_combo.blockSignals(True)
        self.right_layer_combo.blockSignals(True)

        self.left_layer_combo.clear()
        self.right_layer_combo.clear()

        self.left_layer_combo.addItem("-- Select Layer --", None)
        self.right_layer_combo.addItem("-- Select Layer --", None)

        layers = QgsProject.instance().mapLayers().values()
        available_layer_ids = set()

        for layer in layers:
            self.left_layer_combo.addItem(layer.name(), layer.id())
            self.right_layer_combo.addItem(layer.name(), layer.id())
            available_layer_ids.add(layer.id())

        # Check if currently selected layers still exist
        left_exists = current_left in available_layer_ids if current_left else False
        right_exists = current_right in available_layer_ids if current_right else False

        # Restore selection if possible
        if current_left and left_exists:
            idx = self.left_layer_combo.findData(current_left)
            if idx >= 0:
                self.left_layer_combo.setCurrentIndex(idx)
        else:
            # Layer was removed, clear swipe_item reference
            if self.swipe_item.left_layer:
                try:
                    layer_id = self.swipe_item.left_layer.id()
                    if layer_id not in available_layer_ids:
                        self.swipe_item.set_left_layer(None)
                except (RuntimeError, AttributeError):
                    # Layer is invalid, clear it
                    self.swipe_item.set_left_layer(None)

        if current_right and right_exists:
            idx = self.right_layer_combo.findData(current_right)
            if idx >= 0:
                self.right_layer_combo.setCurrentIndex(idx)
        else:
            # Layer was removed, clear swipe_item reference
            if self.swipe_item.right_layer:
                try:
                    layer_id = self.swipe_item.right_layer.id()
                    if layer_id not in available_layer_ids:
                        self.swipe_item.set_right_layer(None)
                except (RuntimeError, AttributeError):
                    # Layer is invalid, clear it
                    self.swipe_item.set_right_layer(None)

        # If swipe is active and a layer was removed, deactivate it
        if self.swipe_item.is_active:
            if not left_exists or not right_exists:
                self.activate_btn.setChecked(False)
                self._on_activate_clicked(False)
                self.status_label.setText("Swipe deactivated - layer was removed")
                self.status_label.setStyleSheet("color: orange; font-size: 10px;")

        self.left_layer_combo.blockSignals(False)
        self.right_layer_combo.blockSignals(False)

    def _on_layers_changed(self, *args):
        """Handle layer changes in the project."""
        # Force immediate refresh
        self._populate_layers()
        self.update()

    def _on_left_layer_changed(self, index):
        """Handle left layer selection change."""
        layer_id = self.left_layer_combo.currentData()
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            self.swipe_item.set_left_layer(layer)
            self._update_status()
        else:
            self.swipe_item.set_left_layer(None)

    def _on_right_layer_changed(self, index):
        """Handle right layer selection change."""
        layer_id = self.right_layer_combo.currentData()
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            self.swipe_item.set_right_layer(layer)
            self._update_status()
        else:
            self.swipe_item.set_right_layer(None)

    def _on_orientation_changed(self, button):
        """Handle orientation change."""
        if self.vertical_radio.isChecked():
            self.swipe_item.set_orientation("vertical")
        else:
            self.swipe_item.set_orientation("horizontal")

    def _on_slider_changed(self, value):
        """Handle position slider change."""
        self.position_label.setText(f"{value}%")
        # Update position and trigger repaint
        self.swipe_item.swipe_position = value / 100.0
        self.swipe_item.update()

    def _on_activate_clicked(self, checked):
        """Handle activate button click."""
        if checked:
            # Validate layer selection
            left_id = self.left_layer_combo.currentData()
            right_id = self.right_layer_combo.currentData()

            if not left_id or not right_id:
                self.activate_btn.setChecked(False)
                self.status_label.setText("Please select both layers first")
                self.status_label.setStyleSheet("color: red; font-size: 10px;")
                return

            if left_id == right_id:
                self.activate_btn.setChecked(False)
                self.status_label.setText("Please select different layers")
                self.status_label.setStyleSheet("color: red; font-size: 10px;")
                return

            # Activate swipe
            self.activate_btn.setText("Deactivate Swipe")
            self.swipe_item.activate()
            self.swipe_tool.install()

            # Only add item if it's not already in the scene
            if self.swipe_item.scene() is None:
                self.canvas.scene().addItem(self.swipe_item)

            self.canvas.refresh()

            self.status_label.setText("Swipe active - drag divider on map")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")

            self.iface.messageBar().pushSuccess(
                "Leafmap", "Swipe tool activated. Drag the divider on the map."
            )
        else:
            # Deactivate swipe
            self.activate_btn.setText("Activate Swipe")
            self.swipe_item.deactivate()
            self.swipe_tool.uninstall()

            try:
                self.canvas.scene().removeItem(self.swipe_item)
            except (RuntimeError, ValueError):
                pass

            self.canvas.refresh()

            self.status_label.setText("Swipe deactivated")
            self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def _swap_layers(self):
        """Swap left and right layer selections."""
        left_idx = self.left_layer_combo.currentIndex()
        right_idx = self.right_layer_combo.currentIndex()

        self.left_layer_combo.setCurrentIndex(right_idx)
        self.right_layer_combo.setCurrentIndex(left_idx)

    def _update_status(self):
        """Update status label based on current state."""
        left_id = self.left_layer_combo.currentData()
        right_id = self.right_layer_combo.currentData()

        if not left_id and not right_id:
            self.status_label.setText("Select both layers to compare")
        elif not left_id:
            self.status_label.setText("Select a left layer")
        elif not right_id:
            self.status_label.setText("Select a right layer")
        elif left_id == right_id:
            self.status_label.setText("Select different layers")
            self.status_label.setStyleSheet("color: orange; font-size: 10px;")
        else:
            self.status_label.setText("Ready - click Activate Swipe")
            self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def showEvent(self, event):
        """Handle dock widget show event - refresh layers when shown."""
        super().showEvent(event)
        # Reconnect signals and refresh when shown
        self._connect_project_signals()
        self._populate_layers()

    def cleanup(self):
        """Clean up resources when dock is closed."""
        # Deactivate swipe if active
        if self.activate_btn.isChecked():
            self.activate_btn.setChecked(False)
            self._on_activate_clicked(False)

        # Uninstall event filters
        self.swipe_tool.uninstall()

    def closeEvent(self, event):
        """Handle dock widget close event."""
        self.cleanup()

        # Disconnect signals
        try:
            QgsProject.instance().layersAdded.disconnect(self._on_layers_changed)
            QgsProject.instance().layersRemoved.disconnect(self._on_layers_changed)
        except (RuntimeError, TypeError):
            pass

        event.accept()
