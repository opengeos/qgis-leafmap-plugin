"""
Export Layer Dock Widget for Leafmap Plugin.

This module provides a dockable panel for exporting XYZ/WMS layers
to Cloud Optimized GeoTIFF (COG) using GDAL.
"""

import io
import math
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qsl, urlsplit, urlencode

import numpy as np
import requests
from PIL import Image

from qgis.PyQt.QtCore import Qt, QCoreApplication
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
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateTransform,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsWkbTypes,
    QgsPointXY,
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsProjectionSelectionWidget

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
except ImportError:  # pragma: no cover - handled with error message
    gdal = None


EARTH_RADIUS = 6378137.0
ORIGIN_SHIFT = 2 * math.pi * EARTH_RADIUS / 2.0
MAX_LATITUDE = 85.05112878


def zoom_level_to_resolution(zoom, tile_size=256):
    """Convert a zoom level to a Web Mercator resolution."""
    return 2 * math.pi * EARTH_RADIUS / (tile_size * 2**zoom)


def resolution_to_zoom_level(resolution, tile_size=256):
    """Convert a Web Mercator resolution to a zoom level."""
    if resolution <= 0:
        raise ValueError("Resolution must be positive")
    zoom = math.log2(2 * math.pi * EARTH_RADIUS / (tile_size * resolution))
    return int(round(zoom))


def deg2num(lat_deg, lon_deg, zoom):
    """Convert latitude/longitude to XYZ tile coordinates (as floats for precision).

    Args:
        lat_deg: Latitude in degrees.
        lon_deg: Longitude in degrees.
        zoom: Zoom level.

    Returns:
        Tuple of (x, y) tile coordinates as floats.
    """
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (
        (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    )
    return xtile, ytile


def num2deg(xtile, ytile, zoom):
    """Convert XYZ tile coordinates to latitude/longitude."""
    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def from4326_to3857(lat, lon):
    """Convert EPSG:4326 coordinates to EPSG:3857.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        Tuple of (x, y) in EPSG:3857 meters.
    """
    x = math.radians(lon) * EARTH_RADIUS
    y = math.log(math.tan(math.radians(45 + lat / 2.0))) * EARTH_RADIUS
    return x, y


def tile_bounds_3857(xtile, ytile, zoom):
    """Return tile bounds in EPSG:3857 for an XYZ tile.

    Args:
        xtile: X tile coordinate.
        ytile: Y tile coordinate.
        zoom: Zoom level.

    Returns:
        Tuple of (min_x, min_y, max_x, max_y) in EPSG:3857.
    """
    lat1, lon1 = num2deg(xtile, ytile, zoom)
    lat2, lon2 = num2deg(xtile + 1, ytile + 1, zoom)
    min_x, max_y = from4326_to3857(lat1, lon1)
    max_x, min_y = from4326_to3857(lat2, lon2)
    return min_x, min_y, max_x, max_y


def download_tile(url, headers, retries=3, timeout=30):
    """Download a single tile image with retries."""
    last_error = None
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                image = Image.open(io.BytesIO(response.content))
                image.load()
                return image
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:  # pragma: no cover - network failures vary
            last_error = exc
    if last_error:
        return None
    return None


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

        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        self.rubber_band.setFillColor(QColor(255, 0, 0, 50))

    def canvasPressEvent(self, event):
        """Handle mouse press event to start drawing."""
        self.start_point = self.toMapCoordinates(event.pos())
        self.end_point = self.start_point
        self.is_drawing = True
        self._update_rubber_band()

    def canvasMoveEvent(self, event):
        """Handle mouse move event to update the bounding box."""
        if self.is_drawing:
            self.end_point = self.toMapCoordinates(event.pos())
            self._update_rubber_band()

    def canvasReleaseEvent(self, event):
        """Handle mouse release event to finish drawing."""
        if self.is_drawing:
            self.end_point = self.toMapCoordinates(event.pos())
            self.is_drawing = False

            extent = QgsRectangle(self.start_point, self.end_point)
            extent.normalize()

            crs = self.canvas.mapSettings().destinationCrs()
            self.callback(extent, crs)

            if self.rubber_band:
                self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

    def _update_rubber_band(self):
        """Update the rubber band visualization."""
        if not self.rubber_band:
            return

        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

        if self.start_point and self.end_point:
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


class ExportDockWidget(QDockWidget):
    """A dockable panel for exporting XYZ/WMS layers."""

    def __init__(self, iface, parent=None):
        """Initialize the export dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Export Layer", parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        self._bbox_tool = None
        self._previous_tool = None
        self._layer_lookup = {}

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._setup_ui()
        self._connect_project_signals()
        self._populate_layers()

    def _setup_ui(self):
        """Set up the dock widget UI."""
        main_widget = QWidget()
        self.setWidget(main_widget)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        header_label = QLabel("Export Layer")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        desc_label = QLabel(
            "Export XYZ/WMS layers to Cloud Optimized GeoTIFF using GDAL."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(desc_label)

        layer_group = QGroupBox("Source Layer")
        layer_layout = QHBoxLayout(layer_group)

        self.layer_combo = QComboBox()
        self.layer_combo.setToolTip("Select XYZ or WMS layer")
        layer_layout.addWidget(self.layer_combo, 1)

        self.refresh_layers_btn = QPushButton("Refresh")
        self.refresh_layers_btn.clicked.connect(self._populate_layers)
        layer_layout.addWidget(self.refresh_layers_btn)

        layout.addWidget(layer_group)

        project_crs = QgsProject.instance().crs()
        bbox_group = QGroupBox(f"Bounding Box (Project CRS: {project_crs.authid()})")
        bbox_layout = QVBoxLayout(bbox_group)

        self.draw_bbox_btn = QPushButton("Draw Bounding Box")
        self.draw_bbox_btn.setCheckable(True)
        self.draw_bbox_btn.setStyleSheet("""
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
        self.draw_bbox_btn.clicked.connect(self._toggle_bbox_mode)
        bbox_layout.addWidget(self.draw_bbox_btn)

        bbox_form = QFormLayout()
        self.min_x_spin = self._create_coordinate_spin()
        self.min_y_spin = self._create_coordinate_spin()
        self.max_x_spin = self._create_coordinate_spin()
        self.max_y_spin = self._create_coordinate_spin()

        bbox_form.addRow("Min X:", self.min_x_spin)
        bbox_form.addRow("Min Y:", self.min_y_spin)
        bbox_form.addRow("Max X:", self.max_x_spin)
        bbox_form.addRow("Max Y:", self.max_y_spin)
        bbox_layout.addLayout(bbox_form)

        layout.addWidget(bbox_group)

        crs_group = QGroupBox("Output CRS")
        crs_layout = QVBoxLayout(crs_group)
        self.crs_selector = QgsProjectionSelectionWidget()
        self.crs_selector.setCrs(QgsProject.instance().crs())
        self.crs_selector.setToolTip("Select output CRS")
        crs_layout.addWidget(self.crs_selector)
        layout.addWidget(crs_group)

        resolution_group = QGroupBox("Resolution")
        resolution_layout = QFormLayout(resolution_group)
        self.resolution_spin = QDoubleSpinBox()
        self.resolution_spin.setRange(0.000001, 1e9)
        self.resolution_spin.setDecimals(6)
        self.resolution_spin.setValue(1.0)
        self.resolution_spin.setToolTip("Pixel size in output CRS units")
        resolution_layout.addRow("Pixel size:", self.resolution_spin)
        layout.addWidget(resolution_group)

        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText(
            "Output COG (.tif) - leave empty for temp file"
        )
        output_layout.addWidget(self.output_path_edit, 1)

        self.output_browse_btn = QPushButton("Browse")
        self.output_browse_btn.clicked.connect(self._browse_output_path)
        output_layout.addWidget(self.output_browse_btn)

        layout.addWidget(output_group)

        self.export_btn = QPushButton("Export COG")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px;
            }
            """)
        self.export_btn.clicked.connect(self._export_layer)
        layout.addWidget(self.export_btn)

        layout.addStretch()

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

    def _create_coordinate_spin(self):
        """Create a coordinate spinbox with consistent settings."""
        spin = QDoubleSpinBox()
        spin.setRange(-1e12, 1e12)
        spin.setDecimals(6)
        spin.setValue(0.0)
        return spin

    def _set_status(self, message, color="gray"):
        """Update the status label."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def _connect_project_signals(self):
        """Connect to project signals for layer updates."""
        project = QgsProject.instance()

        try:
            project.layersAdded.disconnect(self._populate_layers)
        except (RuntimeError, TypeError):
            pass

        try:
            project.layersRemoved.disconnect(self._populate_layers)
        except (RuntimeError, TypeError):
            pass

        project.layersAdded.connect(self._populate_layers)
        project.layersRemoved.connect(self._populate_layers)

    def _is_export_layer(self, layer):
        """Check whether layer is an XYZ/WMS raster layer."""
        if not isinstance(layer, QgsRasterLayer):
            return False

        provider = (layer.providerType() or "").lower()
        if provider in {"wms", "xyz"}:
            return True

        return False

    def _populate_layers(self, *args):
        """Populate the layer dropdown with XYZ/WMS layers."""
        layers = [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if self._is_export_layer(layer)
        ]

        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self._layer_lookup = {}

        if not layers:
            self.layer_combo.addItem("No XYZ/WMS layers found", None)
            self.layer_combo.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.layer_combo.blockSignals(False)
            return

        for layer in layers:
            self.layer_combo.addItem(layer.name(), layer.id())
            self._layer_lookup[layer.id()] = layer

        self.layer_combo.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.layer_combo.blockSignals(False)

    def _browse_output_path(self):
        """Open a file dialog to select output path."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Cloud Optimized GeoTIFF",
            os.path.expanduser("~"),
            "COG Files (*.tif *.tiff);;All Files (*.*)",
        )

        if file_path:
            if not file_path.lower().endswith((".tif", ".tiff")):
                file_path += ".tif"
            self.output_path_edit.setText(file_path)

    def _toggle_bbox_mode(self, checked):
        """Enable or disable bounding box drawing mode."""
        if checked:
            self._previous_tool = self.canvas.mapTool()
            self._bbox_tool = BBoxDrawTool(self.canvas, self._on_bbox_drawn)
            self.canvas.setMapTool(self._bbox_tool)
            self.draw_bbox_btn.setText("Cancel Drawing")
            self._set_status("Click and drag to draw bounding box", "blue")
        else:
            if self._bbox_tool:
                self._bbox_tool.cleanup()

            if self._previous_tool:
                self.canvas.setMapTool(self._previous_tool)
                self._previous_tool = None
            elif self._bbox_tool:
                self.canvas.unsetMapTool(self._bbox_tool)

            self._bbox_tool = None
            self.draw_bbox_btn.setText("Draw Bounding Box")
            self._set_status("Drawing mode deactivated")

    def _on_bbox_drawn(self, extent, source_crs):
        """Handle bounding box drawn on the map canvas."""
        try:
            project_crs = QgsProject.instance().crs()
            if source_crs != project_crs:
                transform = QgsCoordinateTransform(
                    source_crs, project_crs, QgsProject.instance()
                )
                extent = transform.transformBoundingBox(extent)

            self.min_x_spin.setValue(extent.xMinimum())
            self.min_y_spin.setValue(extent.yMinimum())
            self.max_x_spin.setValue(extent.xMaximum())
            self.max_y_spin.setValue(extent.yMaximum())

            if self.draw_bbox_btn.isChecked():
                self.draw_bbox_btn.blockSignals(True)
                self.draw_bbox_btn.setChecked(False)
                self.draw_bbox_btn.blockSignals(False)
                self._toggle_bbox_mode(False)

            self._set_status("Bounding box captured", "green")
        except Exception as e:
            self._set_status(f"Error: {str(e)}", "red")

    def _get_selected_layer(self):
        """Get the currently selected layer."""
        layer_id = self.layer_combo.currentData()
        if layer_id is None:
            return None
        return self._layer_lookup.get(layer_id)

    def _parse_source_params(self, source):
        """Parse a layer source string into a parameter dict."""
        params = {}
        for key, value in parse_qsl(source, keep_blank_values=True):
            params[key] = value
        return params

    def _get_param(self, params, key, default=None):
        """Get a parameter value from parsed source."""
        value = params.get(key)
        if value in (None, ""):
            return default
        return value

    def _build_xyz_xml(self, layer, params, bbox=None, resolution=None):
        """Build GDAL WMS XML for XYZ/TMS layers."""
        url = self._get_param(params, "url")
        if not url:
            raise ValueError("XYZ layer URL is missing")

        url = url.replace("{x}", "${x}").replace("{y}", "${y}").replace("{z}", "${z}")

        tile_size = int(
            self._get_param(
                params, "tileSize", self._get_param(params, "tile_size", 256)
            )
        )

        # Use provided bbox or fallback to layer extent
        if bbox is not None and not bbox.isNull():
            extent = bbox
        else:
            extent = layer.extent()
            if extent.isNull():
                extent = QgsRectangle(
                    -20037508.3427892,
                    -20037508.3427892,
                    20037508.3427892,
                    20037508.3427892,
                )
        extent.normalize()

        crs_authid = layer.crs().authid() or "EPSG:3857"

        # Calculate appropriate zoom level based on resolution
        # For Web Mercator, zoom 0 = 156543 m/pixel at equator
        if resolution and crs_authid == "EPSG:3857":
            import math

            zoom = int(math.log2(156543.03 / resolution))
            zoom = max(0, min(zoom, 14))  # Clamp between 0-14 for safety
        else:
            # Use very conservative zoom to avoid overflow
            zoom = int(self._get_param(params, "zmax", 12))
            zoom = min(zoom, 12)  # Limit to zoom 12 to avoid overflow

        return (
            "<GDAL_WMS>\n"
            '  <Service name="TMS">\n'
            f"    <ServerUrl>{url}</ServerUrl>\n"
            "  </Service>\n"
            "  <DataWindow>\n"
            f"    <UpperLeftX>{extent.xMinimum()}</UpperLeftX>\n"
            f"    <UpperLeftY>{extent.yMaximum()}</UpperLeftY>\n"
            f"    <LowerRightX>{extent.xMaximum()}</LowerRightX>\n"
            f"    <LowerRightY>{extent.yMinimum()}</LowerRightY>\n"
            f"    <TileLevel>{zoom}</TileLevel>\n"
            "    <TileCountX>1</TileCountX>\n"
            "    <TileCountY>1</TileCountY>\n"
            "    <YOrigin>top</YOrigin>\n"
            "  </DataWindow>\n"
            f"  <Projection>{crs_authid}</Projection>\n"
            f"  <BlockSizeX>{tile_size}</BlockSizeX>\n"
            f"  <BlockSizeY>{tile_size}</BlockSizeY>\n"
            "  <BandsCount>3</BandsCount>\n"
            "</GDAL_WMS>\n"
        )

    def _build_wms_xml(self, layer, params, bbox=None):
        """Build GDAL WMS XML for WMS layers."""
        url = self._get_param(params, "url")
        if not url:
            raise ValueError("WMS layer URL is missing")

        if "?" not in url:
            url = f"{url}?"
        elif not url.endswith("?") and not url.endswith("&"):
            url = f"{url}&"

        layers = self._get_param(params, "layers")
        if not layers:
            raise ValueError("WMS layer names are missing")

        styles = self._get_param(params, "styles", "")
        image_format = self._get_param(params, "format", "image/png")
        version = self._get_param(params, "version", "1.1.1")
        crs_authid = (
            self._get_param(params, "crs")
            or self._get_param(params, "srs")
            or layer.crs().authid()
        )

        # Use provided bbox or fallback to layer extent
        if bbox is not None and not bbox.isNull():
            extent = bbox
        else:
            extent = layer.extent()
            if extent.isNull():
                extent = QgsRectangle(-180.0, -90.0, 180.0, 90.0)
        extent.normalize()

        projection_tag = "CRS" if version.startswith("1.3") else "SRS"
        bands = 4 if "png" in image_format.lower() else 3

        return (
            "<GDAL_WMS>\n"
            '  <Service name="WMS">\n'
            f"    <Version>{version}</Version>\n"
            f"    <ServerUrl>{url}</ServerUrl>\n"
            f"    <Layers>{layers}</Layers>\n"
            f"    <Styles>{styles}</Styles>\n"
            f"    <{projection_tag}>{crs_authid}</{projection_tag}>\n"
            f"    <ImageFormat>{image_format}</ImageFormat>\n"
            "  </Service>\n"
            "  <DataWindow>\n"
            f"    <UpperLeftX>{extent.xMinimum()}</UpperLeftX>\n"
            f"    <UpperLeftY>{extent.yMaximum()}</UpperLeftY>\n"
            f"    <LowerRightX>{extent.xMaximum()}</LowerRightX>\n"
            f"    <LowerRightY>{extent.yMinimum()}</LowerRightY>\n"
            "  </DataWindow>\n"
            f"  <Projection>{crs_authid}</Projection>\n"
            "  <BlockSizeX>256</BlockSizeX>\n"
            "  <BlockSizeY>256</BlockSizeY>\n"
            f"  <BandsCount>{bands}</BandsCount>\n"
            "</GDAL_WMS>\n"
        )

    def _estimate_resolution_3857(self, target_crs, bbox, resolution):
        """Estimate the target resolution in EPSG:3857 units."""
        if target_crs.authid() == "EPSG:3857":
            return resolution

        try:
            crs_3857 = QgsCoordinateReferenceSystem("EPSG:3857")
            transform = QgsCoordinateTransform(
                target_crs, crs_3857, QgsProject.instance()
            )
            center = bbox.center()
            offset_x = QgsPointXY(center.x() + resolution, center.y())
            center_3857 = transform.transform(center)
            offset_3857 = transform.transform(offset_x)
            delta = abs(offset_3857.x() - center_3857.x())
            if delta == 0:
                offset_y = QgsPointXY(center.x(), center.y() + resolution)
                offset_3857 = transform.transform(offset_y)
                delta = abs(offset_3857.y() - center_3857.y())
            return delta if delta > 0 else resolution
        except Exception:
            return resolution

    def _build_xyz_tile_url(self, url_template, x, y, zoom, y_origin):
        """Build an XYZ tile URL, handling {-y} and TMS origins."""
        url = url_template
        if "{-y}" in url:
            flipped_y = (2**zoom - 1) - y
            url = url.replace("{-y}", str(flipped_y))
        elif y_origin == "bottom":
            y = (2**zoom - 1) - y
        return (
            url.replace("{x}", str(x)).replace("{y}", str(y)).replace("{z}", str(zoom))
        )

    def _prepare_wms_request(self, params, layer):
        """Prepare WMS base request data."""
        base_url = self._get_param(params, "url")
        if not base_url:
            raise ValueError("WMS layer URL is missing")

        layers = self._get_param(params, "layers")
        if not layers:
            raise ValueError("WMS layer names are missing")

        version = self._get_param(params, "version", "1.1.1")
        styles = self._get_param(params, "styles", "")
        image_format = self._get_param(params, "format", "image/png")
        crs_authid = (
            self._get_param(params, "crs")
            or self._get_param(params, "srs")
            or layer.crs().authid()
        )

        url_parts = urlsplit(base_url)
        base_query = dict(parse_qsl(url_parts.query, keep_blank_values=True))
        base_params = {
            **base_query,
            "SERVICE": "WMS",
            "REQUEST": "GetMap",
            "VERSION": version,
            "LAYERS": layers,
            "STYLES": styles,
            "FORMAT": image_format,
            "TRANSPARENT": "TRUE",
        }
        base = f"{url_parts.scheme}://{url_parts.netloc}{url_parts.path}"
        return base, base_params, version, crs_authid

    def _build_wms_tile_url(
        self,
        base_url,
        base_params,
        version,
        crs_authid,
        tile_bounds,
        tile_size,
    ):
        """Build a WMS GetMap URL for a single tile."""
        min_x, min_y, max_x, max_y = tile_bounds
        crs_param = "CRS" if version.startswith("1.3") else "SRS"
        if version.startswith("1.3") and crs_authid.upper() == "EPSG:4326":
            bbox_value = f"{min_y},{min_x},{max_y},{max_x}"
        else:
            bbox_value = f"{min_x},{min_y},{max_x},{max_y}"

        params = {
            **base_params,
            crs_param: crs_authid,
            "BBOX": bbox_value,
            "WIDTH": str(tile_size),
            "HEIGHT": str(tile_size),
        }
        return f"{base_url}?{urlencode(params)}"

    def _build_gdal_xml(self, layer, bbox=None, resolution=None):
        """Build GDAL WMS XML based on layer type."""
        params = self._parse_source_params(layer.source())
        layer_type = (self._get_param(params, "type") or "").lower()

        if layer.providerType().lower() == "xyz" or layer_type == "xyz":
            return self._build_xyz_xml(layer, params, bbox, resolution)

        return self._build_wms_xml(layer, params, bbox)

    def _create_gdal_dataset(self, xml_string):
        """Create a GDAL dataset from a WMS XML string."""
        if gdal is None:
            raise RuntimeError("GDAL Python bindings are not available")

        mem_path = f"/vsimem/leafmap_wms_{uuid.uuid4().hex}.xml"
        gdal.FileFromMemBuffer(mem_path, xml_string.encode("utf-8"))
        dataset = gdal.Open(mem_path)
        if dataset is None:
            gdal.Unlink(mem_path)
            raise RuntimeError("Failed to open GDAL WMS dataset")

        return dataset, mem_path

    def _export_layer(self):
        """Run the export process."""
        if gdal is None:
            QMessageBox.critical(
                self, "Export Error", "GDAL Python bindings are not available."
            )
            return

        layer = self._get_selected_layer()
        if layer is None or not layer.isValid():
            QMessageBox.warning(self, "Export", "Please select a valid layer.")
            return

        min_x = self.min_x_spin.value()
        min_y = self.min_y_spin.value()
        max_x = self.max_x_spin.value()
        max_y = self.max_y_spin.value()

        if min_x >= max_x or min_y >= max_y:
            QMessageBox.warning(self, "Export", "Invalid bounding box values.")
            return

        resolution = self.resolution_spin.value()
        if resolution <= 0:
            QMessageBox.warning(self, "Export", "Resolution must be positive.")
            return

        output_path = self.output_path_edit.text().strip()
        use_temp_file = False

        if not output_path:
            # Use temporary file if no output path specified
            use_temp_file = True
            temp_fd, output_path = tempfile.mkstemp(suffix=".tif", prefix="leafmap_")
            os.close(temp_fd)
        else:
            if not output_path.lower().endswith((".tif", ".tiff")):
                output_path += ".tif"
                self.output_path_edit.setText(output_path)

            if os.path.exists(output_path):
                reply = QMessageBox.question(
                    self,
                    "Overwrite?",
                    "Output file exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return

            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.isdir(output_dir):
                QMessageBox.warning(self, "Export", "Output directory does not exist.")
                return

        target_crs = self.crs_selector.crs()
        if not target_crs.isValid():
            QMessageBox.warning(self, "Export", "Please select a valid CRS.")
            return

        bbox = QgsRectangle(min_x, min_y, max_x, max_y)
        project_crs = QgsProject.instance().crs()
        if project_crs != target_crs:
            transform = QgsCoordinateTransform(
                project_crs, target_crs, QgsProject.instance()
            )
            bbox = transform.transformBoundingBox(bbox)

        self._set_status("Preparing tile export...", "blue")
        QCoreApplication.processEvents()

        params = self._parse_source_params(layer.source())
        layer_type = (self._get_param(params, "type") or "").lower()
        provider_type = (layer.providerType() or "").lower()
        is_xyz = provider_type == "xyz" or layer_type == "xyz"
        is_wms = provider_type == "wms" or layer_type == "wms"

        if not (is_xyz or is_wms):
            QMessageBox.warning(
                self, "Export", "Please select a valid XYZ or WMS layer."
            )
            return

        tile_size = int(
            self._get_param(
                params, "tileSize", self._get_param(params, "tile_size", 256)
            )
        )
        if tile_size <= 0:
            tile_size = 256

        zoom = None
        zoom_param = self._get_param(params, "zoom") or self._get_param(params, "z")
        if zoom_param:
            try:
                zoom = int(float(zoom_param))
            except ValueError:
                zoom = None

        if zoom is None:
            resolution_3857 = self._estimate_resolution_3857(
                target_crs, bbox, resolution
            )
            zoom = resolution_to_zoom_level(resolution_3857, tile_size)

        zmin = self._get_param(params, "zmin") or self._get_param(params, "zMin")
        zmax = self._get_param(params, "zmax") or self._get_param(params, "zMax")
        if zmin is not None:
            zoom = max(zoom, int(zmin))
        if zmax is not None:
            zoom = min(zoom, int(zmax))
        zoom = max(0, min(zoom, 24))

        bbox_4326 = bbox
        if target_crs.authid() != "EPSG:4326":
            transform_to_4326 = QgsCoordinateTransform(
                target_crs,
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance(),
            )
            bbox_4326 = transform_to_4326.transformBoundingBox(bbox)
        bbox_4326.normalize()

        west = max(-180.0, bbox_4326.xMinimum())
        east = min(180.0, bbox_4326.xMaximum())
        south = max(-MAX_LATITUDE, bbox_4326.yMinimum())
        north = min(MAX_LATITUDE, bbox_4326.yMaximum())

        if west >= east or south >= north:
            QMessageBox.warning(
                self, "Export", "Bounding box is invalid after reprojection."
            )
            return

        # Get fractional tile coordinates (leafmap approach)
        x0, y0 = deg2num(north, west, zoom)
        x1, y1 = deg2num(south, east, zoom)
        x0, x1 = sorted([x0, x1])
        y0, y1 = sorted([y0, y1])

        # Integer tile bounds for downloading
        tile_x_min = math.floor(x0)
        tile_x_max = math.ceil(x1)
        tile_y_min = math.floor(y0)
        tile_y_max = math.ceil(y1)

        tile_requests = []
        base_url = None
        base_params = None
        wms_version = None
        wms_crs_authid = None
        transform_to_layer = None

        if is_xyz:
            url_template = self._get_param(params, "url")
            if not url_template:
                QMessageBox.warning(self, "Export", "XYZ layer URL is missing.")
                return
            y_origin = (
                self._get_param(params, "yOrigin", self._get_param(params, "y_origin"))
                or "top"
            ).lower()
        else:
            try:
                base_url, base_params, wms_version, wms_crs_authid = (
                    self._prepare_wms_request(params, layer)
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Export", str(exc))
                return
            wms_crs = (
                QgsCoordinateReferenceSystem(wms_crs_authid)
                if wms_crs_authid
                else layer.crs()
            )
            if not wms_crs.isValid():
                wms_crs = layer.crs()
            wms_crs_authid = wms_crs.authid()
            if wms_crs_authid != "EPSG:3857":
                transform_to_layer = QgsCoordinateTransform(
                    QgsCoordinateReferenceSystem("EPSG:3857"),
                    wms_crs,
                    QgsProject.instance(),
                )

        for x in range(tile_x_min, tile_x_max):
            for y in range(tile_y_min, tile_y_max):
                if is_xyz:
                    tile_url = self._build_xyz_tile_url(
                        url_template, x, y, zoom, y_origin
                    )
                else:
                    bounds = tile_bounds_3857(x, y, zoom)
                    if transform_to_layer is not None:
                        tile_rect = QgsRectangle(*bounds)
                        tile_rect = transform_to_layer.transformBoundingBox(tile_rect)
                        tile_rect.normalize()
                        bounds = (
                            tile_rect.xMinimum(),
                            tile_rect.yMinimum(),
                            tile_rect.xMaximum(),
                            tile_rect.yMaximum(),
                        )
                    tile_url = self._build_wms_tile_url(
                        base_url,
                        base_params,
                        wms_version,
                        wms_crs_authid,
                        bounds,
                        tile_size,
                    )
                tile_requests.append((x, y, tile_url))

        if not tile_requests:
            QMessageBox.warning(self, "Export", "No tiles found for export.")
            return

        self._set_status(f"Downloading tiles 0/{len(tile_requests)}...", "blue")
        QCoreApplication.processEvents()

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
        }

        dataset = None
        mem_path = None
        try:
            tile_images = {}
            completed = 0
            failed = 0
            max_workers = min(max(4, (os.cpu_count() or 4) * 2), len(tile_requests))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(
                        download_tile, tile_url, headers, retries=3, timeout=30
                    ): (x, y)
                    for x, y, tile_url in tile_requests
                }
                for future in as_completed(future_map):
                    x, y = future_map[future]
                    image = future.result()
                    if image is not None:
                        tile_images[(x, y)] = image.convert("RGBA")
                    else:
                        failed += 1
                    completed += 1
                    if completed % 5 == 0 or completed == len(tile_requests):
                        self._set_status(
                            f"Downloading tiles {completed}/{len(tile_requests)}...",
                            "blue",
                        )
                        QCoreApplication.processEvents()

            if not tile_images:
                raise RuntimeError("No tiles downloaded successfully.")

            if failed:
                self.iface.messageBar().pushWarning(
                    "Leafmap",
                    f"{failed} tiles failed to download; missing areas will be blank.",
                )

            self._set_status("Stitching tiles...", "blue")
            QCoreApplication.processEvents()

            # Create mosaic from downloaded tiles
            mosaic_width = (tile_x_max - tile_x_min) * tile_size
            mosaic_height = (tile_y_max - tile_y_min) * tile_size
            mosaic = Image.new(
                "RGBA", (mosaic_width, mosaic_height), (255, 255, 255, 0)
            )
            blank_tile = Image.new("RGBA", (tile_size, tile_size), (255, 255, 255, 0))

            for y in range(tile_y_min, tile_y_max):
                for x in range(tile_x_min, tile_x_max):
                    tile = tile_images.get((x, y), blank_tile)
                    offset_x = (x - tile_x_min) * tile_size
                    offset_y = (y - tile_y_min) * tile_size
                    mosaic.paste(tile, (offset_x, offset_y))

            # Crop mosaic to exact bbox (leafmap approach)
            # Calculate pixel offsets for cropping
            xfrac = x0 - tile_x_min
            yfrac = y0 - tile_y_min
            crop_x0 = round(tile_size * xfrac)
            crop_y0 = round(tile_size * yfrac)
            crop_width = round(tile_size * (x1 - x0))
            crop_height = round(tile_size * (y1 - y0))

            # Crop to exact bbox
            cropped = mosaic.crop(
                (crop_x0, crop_y0, crop_x0 + crop_width, crop_y0 + crop_height)
            )

            # Convert to RGB if alpha is fully opaque
            if cropped.mode == "RGBA":
                extrema = cropped.getextrema()
                if len(extrema) > 3 and extrema[3] == (255, 255):
                    cropped = cropped.convert("RGB")

            mosaic.close()

            self._set_status("Creating GeoTIFF...", "blue")
            QCoreApplication.processEvents()

            # Calculate geotransform from actual bbox in Web Mercator
            xp0, yp0 = from4326_to3857(south, west)
            xp1, yp1 = from4326_to3857(north, east)
            pwidth = abs(xp1 - xp0) / cropped.size[0]
            pheight = abs(yp1 - yp0) / cropped.size[1]
            geotransform = (
                min(xp0, xp1),
                pwidth,
                0.0,
                max(yp0, yp1),
                0.0,
                -pheight,
            )

            mem_path = f"/vsimem/leafmap_tiles_{uuid.uuid4().hex}.tif"
            driver = gdal.GetDriverByName("GTiff")
            img_bands = len(cropped.getbands())
            dataset = driver.Create(
                mem_path, cropped.size[0], cropped.size[1], img_bands, gdal.GDT_Byte
            )
            dataset.SetGeoTransform(geotransform)
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(3857)
            dataset.SetProjection(srs.ExportToWkt())

            # Write bands to dataset
            for band_idx in range(img_bands):
                band_array = np.array(cropped.getdata(band_idx), dtype="u8")
                band_array = band_array.reshape((cropped.size[1], cropped.size[0]))
                dataset.GetRasterBand(band_idx + 1).WriteArray(band_array)
            if img_bands == 4:
                dataset.GetRasterBand(4).SetColorInterpretation(gdal.GCI_AlphaBand)
            dataset.FlushCache()
            cropped.close()

            creation_options = [
                "COMPRESS=LZW",
                "BIGTIFF=IF_SAFER",
                "BLOCKSIZE=512",
            ]

            warp_options = gdal.WarpOptions(
                format="COG",
                outputBounds=(
                    bbox.xMinimum(),
                    bbox.yMinimum(),
                    bbox.xMaximum(),
                    bbox.yMaximum(),
                ),
                outputBoundsSRS=target_crs.authid(),
                dstSRS=target_crs.authid(),
                xRes=resolution,
                yRes=resolution,
                resampleAlg="bilinear",
                multithread=True,
                creationOptions=creation_options,
            )

            result = gdal.Warp(output_path, dataset, options=warp_options)

            if result is None:
                raise RuntimeError("GDAL export failed.")

            result = None
            self._set_status("Export completed", "green")

            if use_temp_file:
                # Add temporary file as a layer in QGIS
                layer_name = layer.name() + "_export"
                raster_layer = QgsRasterLayer(output_path, layer_name)
                if raster_layer.isValid():
                    QgsProject.instance().addMapLayer(raster_layer)
                    self.iface.messageBar().pushSuccess(
                        "Leafmap", f"Added exported layer: {layer_name}"
                    )
                else:
                    self.iface.messageBar().pushWarning(
                        "Leafmap", f"Exported to {output_path} but failed to add layer"
                    )
            else:
                self.iface.messageBar().pushSuccess(
                    "Leafmap", f"Exported COG to {output_path}"
                )

        except Exception as e:
            self._set_status(f"Error: {str(e)}", "red")
            QMessageBox.critical(self, "Export Error", str(e))
        finally:
            if dataset is not None:
                dataset = None
            if mem_path:
                gdal.Unlink(mem_path)

    def cleanup(self):
        """Clean up map tools when dock is closed."""
        if self.draw_bbox_btn.isChecked():
            self.draw_bbox_btn.setChecked(False)
            self._toggle_bbox_mode(False)

        if self._bbox_tool:
            self._bbox_tool.cleanup()
            self._bbox_tool = None
