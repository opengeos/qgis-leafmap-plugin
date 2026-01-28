"""
Coordinate Retrieval Dock Widget for Leafmap Plugin

This module provides a dock widget for retrieving coordinates from:
- Mouse clicks on the map
- Current map extent
- Drawn bounding boxes

All coordinates can be transformed to a user-specified CRS.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QApplication,
    QTextEdit,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
    QgsRectangle,
    QgsWkbTypes,
)
from qgis.gui import (
    QgsMapTool,
    QgsMapToolEmitPoint,
    QgsRubberBand,
    QgsProjectionSelectionWidget,
)


class ClickCoordinateTool(QgsMapToolEmitPoint):
    """Map tool that captures click coordinates on the map canvas."""

    def __init__(self, canvas, callback):
        """Initialize the click coordinate tool.

        Args:
            canvas: QgsMapCanvas instance.
            callback: Function to call with the clicked point and CRS.
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.callback = callback

    def canvasReleaseEvent(self, event):
        """Handle mouse release event on the canvas.

        Args:
            event: QgsMapMouseEvent instance.
        """
        point = self.toMapCoordinates(event.pos())
        crs = self.canvas.mapSettings().destinationCrs()
        self.callback(point, crs)


class BBoxDrawTool(QgsMapTool):
    """Map tool for drawing bounding boxes on the map canvas."""

    def __init__(self, canvas, callback):
        """Initialize the bounding box drawing tool.

        Args:
            canvas: QgsMapCanvas instance.
            callback: Function to call with the drawn extent and CRS.
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.callback = callback
        self.start_point = None
        self.end_point = None
        self.is_drawing = False

        # Create rubber band for visual feedback
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        self.rubber_band.setFillColor(QColor(255, 0, 0, 50))

    def canvasPressEvent(self, event):
        """Handle mouse press event to start drawing.

        Args:
            event: QgsMapMouseEvent instance.
        """
        self.start_point = self.toMapCoordinates(event.pos())
        self.end_point = self.start_point
        self.is_drawing = True
        self._update_rubber_band()

    def canvasMoveEvent(self, event):
        """Handle mouse move event to update the bounding box.

        Args:
            event: QgsMapMouseEvent instance.
        """
        if self.is_drawing:
            self.end_point = self.toMapCoordinates(event.pos())
            self._update_rubber_band()

    def canvasReleaseEvent(self, event):
        """Handle mouse release event to finish drawing.

        Args:
            event: QgsMapMouseEvent instance.
        """
        if self.is_drawing:
            self.end_point = self.toMapCoordinates(event.pos())
            self.is_drawing = False

            # Create extent from points
            extent = QgsRectangle(self.start_point, self.end_point)
            extent.normalize()

            crs = self.canvas.mapSettings().destinationCrs()
            self.callback(extent, crs)

            # Clear rubber band after short delay to show the final bbox
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

    def _update_rubber_band(self):
        """Update the rubber band visualization."""
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

        if self.start_point and self.end_point:
            # Create rectangle points
            p1 = self.start_point
            p2 = QgsPointXY(self.end_point.x(), self.start_point.y())
            p3 = self.end_point
            p4 = QgsPointXY(self.start_point.x(), self.end_point.y())

            self.rubber_band.addPoint(p1, False)
            self.rubber_band.addPoint(p2, False)
            self.rubber_band.addPoint(p3, False)
            self.rubber_band.addPoint(p4, True)

    def cleanup(self):
        """Clean up the rubber band."""
        if self.rubber_band:
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self.canvas.scene().removeItem(self.rubber_band)
            self.rubber_band = None

    def deactivate(self):
        """Deactivate the tool and clean up."""
        if self.rubber_band:
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        super().deactivate()


class CoordinatesDockWidget(QDockWidget):
    """A dockable panel for retrieving and transforming coordinates."""

    def __init__(self, iface, parent=None):
        """Initialize the dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Coordinate Retrieval", parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Map tools
        self._click_tool = None
        self._bbox_tool = None
        self._previous_tool = None

        self._setup_ui()

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
        header_label = QLabel("Coordinate Retrieval")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            "Retrieve coordinates from map clicks, current extent, "
            "or drawn bounding boxes. Transform to any CRS."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(desc_label)

        # Settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout(settings_group)

        # CRS selector
        self.crs_selector = QgsProjectionSelectionWidget()
        self.crs_selector.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.crs_selector.setToolTip("Target CRS for coordinate output")
        settings_layout.addRow("Target CRS:", self.crs_selector)

        # Output format dropdown
        self.format_combo = QComboBox()
        self.format_combo.addItem("xmin, ymin, xmax, ymax", "comma")
        self.format_combo.addItem("[xmin, ymin, xmax, ymax]", "list")
        self.format_combo.addItem('{"west": xmin, ...}', "dict")
        self.format_combo.addItem("(xmin, ymin, xmax, ymax)", "tuple")
        self.format_combo.addItem("bounds=[xmin, ymin, xmax, ymax]", "bounds")
        self.format_combo.addItem("POLYGON(...)", "wkt")
        self.format_combo.setToolTip("Output format for coordinates")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        settings_layout.addRow("Format:", self.format_combo)

        # Decimal precision spinner
        self.precision_spinner = QSpinBox()
        self.precision_spinner.setRange(0, 15)
        self.precision_spinner.setValue(6)
        self.precision_spinner.setToolTip("Decimal places for coordinates")
        self.precision_spinner.valueChanged.connect(self._on_precision_changed)
        settings_layout.addRow("Decimal Places:", self.precision_spinner)

        layout.addWidget(settings_group)

        # Point coordinates group
        point_group = QGroupBox("Point Coordinates")
        point_layout = QVBoxLayout(point_group)

        # Click mode toggle button
        self.click_mode_btn = QPushButton("Activate Click Mode")
        self.click_mode_btn.setCheckable(True)
        self.click_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
        """)
        self.click_mode_btn.clicked.connect(self._toggle_click_mode)
        point_layout.addWidget(self.click_mode_btn)

        # X coordinate display
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        self.x_edit = QLineEdit()
        self.x_edit.setReadOnly(True)
        self.x_edit.setPlaceholderText("Click on map")
        x_layout.addWidget(self.x_edit)
        self.copy_x_btn = QPushButton("Copy")
        self.copy_x_btn.setFixedWidth(50)
        self.copy_x_btn.clicked.connect(lambda: self._copy_to_clipboard(self.x_edit))
        x_layout.addWidget(self.copy_x_btn)
        point_layout.addLayout(x_layout)

        # Y coordinate display
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        self.y_edit = QLineEdit()
        self.y_edit.setReadOnly(True)
        self.y_edit.setPlaceholderText("Click on map")
        y_layout.addWidget(self.y_edit)
        self.copy_y_btn = QPushButton("Copy")
        self.copy_y_btn.setFixedWidth(50)
        self.copy_y_btn.clicked.connect(lambda: self._copy_to_clipboard(self.y_edit))
        y_layout.addWidget(self.copy_y_btn)
        point_layout.addLayout(y_layout)

        # Copy both coordinates
        self.copy_point_btn = QPushButton("Copy X, Y")
        self.copy_point_btn.clicked.connect(self._copy_point_coordinates)
        point_layout.addWidget(self.copy_point_btn)

        layout.addWidget(point_group)

        # Map extent group
        extent_group = QGroupBox("Map Extent")
        extent_layout = QVBoxLayout(extent_group)

        self.get_extent_btn = QPushButton("Get Current Extent")
        self.get_extent_btn.clicked.connect(self._get_map_extent)
        extent_layout.addWidget(self.get_extent_btn)

        self.extent_edit = QTextEdit()
        self.extent_edit.setReadOnly(True)
        self.extent_edit.setMaximumHeight(60)
        self.extent_edit.setPlaceholderText("Click button to get extent")
        extent_layout.addWidget(self.extent_edit)

        copy_extent_layout = QHBoxLayout()
        self.copy_extent_btn = QPushButton("Copy Extent")
        self.copy_extent_btn.clicked.connect(
            lambda: self._copy_to_clipboard(self.extent_edit)
        )
        copy_extent_layout.addWidget(self.copy_extent_btn)
        extent_layout.addLayout(copy_extent_layout)

        layout.addWidget(extent_group)

        # Bounding box group
        bbox_group = QGroupBox("Draw Bounding Box")
        bbox_layout = QVBoxLayout(bbox_group)

        self.bbox_mode_btn = QPushButton("Draw Bounding Box")
        self.bbox_mode_btn.setCheckable(True)
        self.bbox_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
        """)
        self.bbox_mode_btn.clicked.connect(self._toggle_bbox_mode)
        bbox_layout.addWidget(self.bbox_mode_btn)

        self.bbox_edit = QTextEdit()
        self.bbox_edit.setReadOnly(True)
        self.bbox_edit.setMaximumHeight(60)
        self.bbox_edit.setPlaceholderText("Draw on map to get bounds")
        bbox_layout.addWidget(self.bbox_edit)

        copy_bbox_layout = QHBoxLayout()
        self.copy_bbox_btn = QPushButton("Copy Bounds")
        self.copy_bbox_btn.clicked.connect(
            lambda: self._copy_to_clipboard(self.bbox_edit)
        )
        copy_bbox_layout.addWidget(self.copy_bbox_btn)
        bbox_layout.addLayout(copy_bbox_layout)

        layout.addWidget(bbox_group)

        # Stretch
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _get_selected_crs(self):
        """Get the target CRS from the selector.

        Returns:
            QgsCoordinateReferenceSystem: The selected target CRS.
        """
        return self.crs_selector.crs()

    def _transform_point(self, point, source_crs):
        """Transform a point to the target CRS.

        Args:
            point: QgsPointXY to transform.
            source_crs: Source QgsCoordinateReferenceSystem.

        Returns:
            QgsPointXY: Transformed point.
        """
        target_crs = self._get_selected_crs()
        if source_crs == target_crs:
            return point

        transform = QgsCoordinateTransform(
            source_crs, target_crs, QgsProject.instance()
        )
        return transform.transform(point)

    def _transform_extent(self, extent, source_crs):
        """Transform an extent to the target CRS.

        Args:
            extent: QgsRectangle to transform.
            source_crs: Source QgsCoordinateReferenceSystem.

        Returns:
            QgsRectangle: Transformed extent.
        """
        target_crs = self._get_selected_crs()
        if source_crs == target_crs:
            return extent

        transform = QgsCoordinateTransform(
            source_crs, target_crs, QgsProject.instance()
        )
        return transform.transformBoundingBox(extent)

    def _format_coordinates(self, xmin, ymin, xmax=None, ymax=None, is_point=False):
        """Format coordinates based on selected format.

        Args:
            xmin: X minimum (or X for points).
            ymin: Y minimum (or Y for points).
            xmax: X maximum (for extents/bboxes).
            ymax: Y maximum (for extents/bboxes).
            is_point: Whether this is a single point.

        Returns:
            str: Formatted coordinate string.
        """
        precision = self.precision_spinner.value()
        format_type = self.format_combo.currentData()

        if is_point:
            # For points, just return x, y
            return f"{xmin:.{precision}f}, {ymin:.{precision}f}"

        # Format extent/bbox
        xmin_f = f"{xmin:.{precision}f}"
        ymin_f = f"{ymin:.{precision}f}"
        xmax_f = f"{xmax:.{precision}f}"
        ymax_f = f"{ymax:.{precision}f}"

        if format_type == "comma":
            return f"{xmin_f}, {ymin_f}, {xmax_f}, {ymax_f}"
        elif format_type == "list":
            return f"[{xmin_f}, {ymin_f}, {xmax_f}, {ymax_f}]"
        elif format_type == "dict":
            return (
                f'{{"west": {xmin_f}, "south": {ymin_f}, '
                f'"east": {xmax_f}, "north": {ymax_f}}}'
            )
        elif format_type == "tuple":
            return f"({xmin_f}, {ymin_f}, {xmax_f}, {ymax_f})"
        elif format_type == "bounds":
            return f"bounds=[{xmin_f}, {ymin_f}, {xmax_f}, {ymax_f}]"
        elif format_type == "wkt":
            return (
                f"POLYGON(({xmin_f} {ymin_f}, {xmax_f} {ymin_f}, "
                f"{xmax_f} {ymax_f}, {xmin_f} {ymax_f}, {xmin_f} {ymin_f}))"
            )
        else:
            return f"{xmin_f}, {ymin_f}, {xmax_f}, {ymax_f}"

    def _toggle_click_mode(self, checked):
        """Enable or disable click coordinate capture mode.

        Args:
            checked: Whether the button is checked.
        """
        if checked:
            # Deactivate bbox mode if active
            if self.bbox_mode_btn.isChecked():
                self.bbox_mode_btn.setChecked(False)
                self._toggle_bbox_mode(False)

            # Store previous tool
            self._previous_tool = self.canvas.mapTool()

            # Create and set click tool
            self._click_tool = ClickCoordinateTool(self.canvas, self._on_point_clicked)
            self.canvas.setMapTool(self._click_tool)

            self.click_mode_btn.setText("Deactivate Click Mode")
            self.status_label.setText("Click on map to get coordinates")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
        else:
            # Restore previous tool
            if self._previous_tool:
                self.canvas.setMapTool(self._previous_tool)
                self._previous_tool = None
            else:
                self.canvas.unsetMapTool(self._click_tool)

            self._click_tool = None
            self.click_mode_btn.setText("Activate Click Mode")
            self.status_label.setText("Click mode deactivated")
            self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def _toggle_bbox_mode(self, checked):
        """Enable or disable bounding box drawing mode.

        Args:
            checked: Whether the button is checked.
        """
        if checked:
            # Deactivate click mode if active
            if self.click_mode_btn.isChecked():
                self.click_mode_btn.setChecked(False)
                self._toggle_click_mode(False)

            # Store previous tool
            self._previous_tool = self.canvas.mapTool()

            # Create and set bbox tool
            self._bbox_tool = BBoxDrawTool(self.canvas, self._on_bbox_drawn)
            self.canvas.setMapTool(self._bbox_tool)

            self.bbox_mode_btn.setText("Cancel Drawing")
            self.status_label.setText("Click and drag to draw bounding box")
            self.status_label.setStyleSheet("color: blue; font-size: 10px;")
        else:
            # Clean up bbox tool
            if self._bbox_tool:
                self._bbox_tool.cleanup()

            # Restore previous tool
            if self._previous_tool:
                self.canvas.setMapTool(self._previous_tool)
                self._previous_tool = None
            elif self._bbox_tool:
                self.canvas.unsetMapTool(self._bbox_tool)

            self._bbox_tool = None
            self.bbox_mode_btn.setText("Draw Bounding Box")
            self.status_label.setText("Drawing mode deactivated")
            self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def _on_point_clicked(self, point, source_crs):
        """Handle a point being clicked on the map.

        Args:
            point: QgsPointXY that was clicked.
            source_crs: CRS of the clicked point.
        """
        try:
            transformed = self._transform_point(point, source_crs)
            precision = self.precision_spinner.value()

            self.x_edit.setText(f"{transformed.x():.{precision}f}")
            self.y_edit.setText(f"{transformed.y():.{precision}f}")

            target_crs = self._get_selected_crs()
            self.status_label.setText(f"Point captured ({target_crs.authid()})")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")

    def _on_bbox_drawn(self, extent, source_crs):
        """Handle a bounding box being drawn on the map.

        Args:
            extent: QgsRectangle that was drawn.
            source_crs: CRS of the drawn extent.
        """
        try:
            transformed = self._transform_extent(extent, source_crs)

            formatted = self._format_coordinates(
                transformed.xMinimum(),
                transformed.yMinimum(),
                transformed.xMaximum(),
                transformed.yMaximum(),
            )

            self.bbox_edit.setText(formatted)

            target_crs = self._get_selected_crs()
            self.status_label.setText(f"Bounding box captured ({target_crs.authid()})")
            self.status_label.setStyleSheet("color: blue; font-size: 10px;")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")

    def _get_map_extent(self):
        """Get and display the current map extent."""
        try:
            extent = self.canvas.extent()
            source_crs = self.canvas.mapSettings().destinationCrs()

            transformed = self._transform_extent(extent, source_crs)

            formatted = self._format_coordinates(
                transformed.xMinimum(),
                transformed.yMinimum(),
                transformed.xMaximum(),
                transformed.yMaximum(),
            )

            self.extent_edit.setText(formatted)

            target_crs = self._get_selected_crs()
            self.status_label.setText(f"Extent retrieved ({target_crs.authid()})")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")

    def _copy_to_clipboard(self, widget):
        """Copy text from a widget to the clipboard.

        Args:
            widget: QLineEdit or QTextEdit to copy from.
        """
        if isinstance(widget, QLineEdit):
            text = widget.text()
        else:
            text = widget.toPlainText()

        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Copied to clipboard")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.status_label.setText("Nothing to copy")
            self.status_label.setStyleSheet("color: orange; font-size: 10px;")

    def _copy_point_coordinates(self):
        """Copy both X and Y coordinates to clipboard."""
        x = self.x_edit.text()
        y = self.y_edit.text()

        if x and y:
            text = f"{x}, {y}"
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Point coordinates copied")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
        else:
            self.status_label.setText("No point coordinates to copy")
            self.status_label.setStyleSheet("color: orange; font-size: 10px;")

    def _on_format_changed(self, index):
        """Handle format selection change - update displayed coordinates.

        Args:
            index: New combo box index.
        """
        # Re-format extent if available
        if self.extent_edit.toPlainText():
            self._get_map_extent()

    def _on_precision_changed(self, value):
        """Handle precision change - update displayed coordinates.

        Args:
            value: New precision value.
        """
        # Re-format extent if available
        if self.extent_edit.toPlainText():
            self._get_map_extent()

        # Update point coordinates if available
        if self.x_edit.text() and self.y_edit.text():
            try:
                x = float(self.x_edit.text())
                y = float(self.y_edit.text())
                self.x_edit.setText(f"{x:.{value}f}")
                self.y_edit.setText(f"{y:.{value}f}")
            except ValueError:
                pass

    def cleanup(self):
        """Clean up map tools and resources."""
        # Deactivate click mode
        if self.click_mode_btn.isChecked():
            self.click_mode_btn.setChecked(False)
            self._toggle_click_mode(False)

        # Deactivate bbox mode
        if self.bbox_mode_btn.isChecked():
            self.bbox_mode_btn.setChecked(False)
            self._toggle_bbox_mode(False)

        # Clean up tools
        if self._bbox_tool:
            self._bbox_tool.cleanup()
            self._bbox_tool = None

        self._click_tool = None

    def closeEvent(self, event):
        """Handle dock widget close event.

        Args:
            event: QCloseEvent instance.
        """
        self.cleanup()
        event.accept()
