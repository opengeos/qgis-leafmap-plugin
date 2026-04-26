# Leafmap QGIS Plugin

A powerful QGIS plugin for interactive layer visualization and comparison, inspired by the [leafmap](https://github.com/opengeos/leafmap) Python package.

![](https://github.com/user-attachments/assets/082acb93-b954-4321-83cf-ff2af3356e9b)

## Features

- **Layer Transparency Control**: Interactive slider to adjust layer transparency in real-time for all loaded layers
- **Layer Swipe Tool**: Compare two layers side-by-side with a draggable divider (similar to ipyleaflet split control)
- **Dockable Panels**: All tools are available as dockable panels that can be positioned anywhere in the QGIS interface
- **Plugin Update Checker**: Check for updates from GitHub and install them automatically
- **Settings Panel**: Configure plugin options with persistent storage

## Screenshots

### Layer Transparency Panel
Control the transparency of all layers with individual sliders. Filter by layer type (raster/vector) and visibility.

![](https://github.com/user-attachments/assets/f431f51e-0584-4a1a-88d2-b9cd32a1eefc)

### Layer Swipe Tool
Compare two layers by swiping between them. Select left and right layers, choose vertical or horizontal orientation, and drag the divider on the map.

![](https://github.com/user-attachments/assets/303755af-ed5b-4105-ac85-795f0bc7e750)

## Video Tutorial

👉 [Compare Layers Visually in QGIS — New Leafmap Plugin Demo!](https://youtu.be/glBgnyS8IDY)

[![Leafmap QGIS Plugin](https://github.com/user-attachments/assets/c6468f4e-4fbf-4f29-865f-041dcd13d9d4)](https://youtu.be/glBgnyS8IDY)



## Requirements

- QGIS 3.28 or later (including QGIS 4.0)
- Python 3.10+

## Installation

### Option A: QGIS Plugin Manager (Recommended)

1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins...**
3. Go to the **Settings** tab
4. Click **Add...** under "Plugin Repositories"
5. Give a name for the repository, e.g., "OpenGeos"
6. Enter the URL of the repository: https://qgis.gishub.org/plugins.xml
7. Click **OK**
8. Go to the **All** tab
9. Search for "Leafmap"
10. Select the plugin and click **Install Plugin**

### Option B: Install Script

Using Python:
```bash
# Clone the repository
git clone https://github.com/opengeos/qgis-leafmap-plugin.git
cd qgis-leafmap-plugin

# Install
python install.py

# Or remove
python install.py --remove
```

Using Bash:
```bash
# Make executable (first time only)
chmod +x install.sh

# Install
./install.sh

# Or remove
./install.sh --remove
```

### Option C: Manual Installation

Copy the `qgis_leafmap` folder to your QGIS plugins directory:

- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

## Usage

### Layer Transparency

1. Click the **Layer Transparency** button in the toolbar or go to **Leafmap** → **Layer Transparency**
2. A dockable panel will appear with sliders for each layer
3. Drag the slider to adjust transparency (0% = opaque, 100% = transparent)
4. Use the filter options to show only raster or vector layers
5. Use "Reset All" to restore all layers to 0% transparency

### Layer Swipe Tool

1. Click the **Layer Swipe** button in the toolbar or go to **Leafmap** → **Layer Swipe**
2. Select the **Left Layer** (shown on left side of divider)
3. Select the **Right Layer** (shown on right side of divider)
4. Choose **Vertical** or **Horizontal** orientation
5. Click **Activate Swipe**
6. Drag the divider on the map to compare layers
7. Use the slider or quick buttons to adjust the divider position
8. Click **Deactivate Swipe** when done

### Settings

1. Go to **Leafmap** → **Settings**
2. Adjust general, transparency, and swipe tool options
3. Click **Save Settings** to persist changes

### Check for Updates

1. Go to **Leafmap** → **Check for Updates...**
2. Click **Check for Updates** to see if a new version is available
3. If an update is available, click **Download and Install Update**
4. Restart QGIS to apply the update

## Project Structure

```
qgis-leafmap-plugin/
├── qgis_leafmap/
│   ├── __init__.py              # Plugin entry point
│   ├── qgis_leafmap.py          # Main plugin class
│   ├── metadata.txt             # Plugin metadata for QGIS
│   ├── LICENSE                  # Plugin license
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── transparency_dock.py # Layer transparency panel
│   │   ├── swipe_dock.py        # Layer swipe/comparison tool
│   │   ├── settings_dock.py     # Settings panel
│   │   └── update_checker.py    # Update checker dialog
│   └── icons/
│       ├── icon.svg             # Main plugin icon
│       ├── transparency.svg     # Transparency tool icon
│       ├── swipe.svg            # Swipe tool icon
│       ├── settings.svg         # Settings icon
│       └── about.svg            # About icon
├── package_plugin.py            # Python packaging script
├── package_plugin.sh            # Bash packaging script
├── install.py                   # Python installation script
├── install.sh                   # Bash installation script
├── README.md                    # This file
└── LICENSE                      # Repository license
```

## Development

### Testing with Conda Environment

For testing with the `geo` conda environment:

```bash
# Activate the geo environment
conda activate geo

# Install the plugin
python install.py

# Start QGIS from the terminal to see any error messages
qgis
```

### Adding New Features

1. Create new dock widgets in the `dialogs/` folder
2. Add corresponding toggle methods in `qgis_leafmap.py`
3. Create icons in the `icons/` folder
4. Update `dialogs/__init__.py` with new imports

## Packaging for QGIS Plugin Repository

### Using Python Script

```bash
# Default packaging
python package_plugin.py

# Custom output path
python package_plugin.py --output /path/to/qgis_leafmap.zip

# Without version in filename
python package_plugin.py --no-version
```

### Using Bash Script

```bash
# Make executable (first time only)
chmod +x package_plugin.sh

# Default packaging
./package_plugin.sh

# Custom output directory
./package_plugin.sh --output /path/to/output
```

### Uploading to QGIS Plugin Repository

1. Create an account at [plugins.qgis.org](https://plugins.qgis.org/)
2. Go to "My plugins" and click "Add a new plugin"
3. Upload the generated zip file
4. Fill in the required information
5. Submit for review

## Related Projects

- [leafmap](https://github.com/opengeos/leafmap) - A Python package for interactive mapping and geospatial analysis
- [ipyleaflet](https://github.com/jupyter-widgets/ipyleaflet) - A Jupyter widget for Leaflet.js interactive maps
- [geemap](https://github.com/gee-community/geemap) - A Python package for interactive mapping with Google Earth Engine

## License

This plugin is released under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Links

- [GitHub Repository](https://github.com/opengeos/qgis-leafmap-plugin)
- [Report Issues](https://github.com/opengeos/qgis-leafmap-plugin/issues)
- [Leafmap Documentation](https://leafmap.org)
- [QGIS Plugin Development Documentation](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
