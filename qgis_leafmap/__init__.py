"""
Leafmap QGIS Plugin

A QGIS plugin for interactive layer comparison with transparency control
and swipe tools, inspired by the leafmap Python package.
"""

from .qgis_leafmap import QgisLeafmap


def classFactory(iface):
    """Load QgisLeafmap class from file qgis_leafmap.

    Args:
        iface: A QGIS interface instance.

    Returns:
        QgisLeafmap: The plugin instance.
    """
    return QgisLeafmap(iface)
