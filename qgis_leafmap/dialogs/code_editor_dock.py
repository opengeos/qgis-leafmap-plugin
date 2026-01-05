"""
Python Code Editor Dock Widget for Leafmap Plugin

This module provides an interactive Python code editor with execution capabilities,
allowing users to write and run PyQGIS scripts with full access to the QGIS interface.
"""

import os
import sys
from io import StringIO

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QAction,
    QSplitter,
    QTextEdit,
    QLabel,
    QFileDialog,
    QMessageBox,
    QShortcut,
)
from qgis.PyQt.QtGui import QIcon, QColor, QKeySequence, QKeyEvent
from qgis.gui import QgsCodeEditorPython
from qgis.core import QgsProject


class CodeEditorDockWidget(QDockWidget):
    """A Python code editor dock widget with QGIS execution capabilities."""

    SETTINGS_PREFIX = "Leafmap/CodeEditor/"

    def __init__(self, iface, parent=None):
        """Initialize the code editor dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Python Editor", parent)
        self.iface = iface
        self.settings = QSettings()

        # File management
        self.current_file_path = None
        self.is_modified = False

        # UI components
        self.editor = None
        self.output_panel = None
        self.toolbar = None
        self.status_label = None
        self.splitter = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._setup_ui()
        self._setup_shortcuts()

    def _setup_ui(self):
        """Set up the dock widget UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Main layout
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Splitter for editor and output
        self.splitter = QSplitter(Qt.Vertical)

        # Editor
        self.editor = self._setup_editor()
        self.splitter.addWidget(self.editor)

        # Output panel
        self.output_panel = self._setup_output_panel()
        self.splitter.addWidget(self.output_panel)

        # Set initial sizes (60% editor, 40% output)
        self.splitter.setSizes([600, 400])

        layout.addWidget(self.splitter)

        # Status bar
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(5, 2, 5, 2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.file_label = QLabel("untitled.py")
        self.file_label.setStyleSheet("color: gray; font-size: 10px;")
        status_layout.addWidget(self.file_label)

        layout.addWidget(status_widget)

        # Set initial title
        self._update_title()

    def _create_toolbar(self):
        """Create and configure toolbar with action buttons."""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # New file
        new_action = QAction(
            QIcon(":/images/themes/default/mActionFileNew.svg"), "New", self
        )
        new_action.setToolTip("New file (Ctrl+N)")
        new_action.triggered.connect(self._new_file)
        toolbar.addAction(new_action)

        # Open file
        open_action = QAction(
            QIcon(":/images/themes/default/mActionFileOpen.svg"), "Open", self
        )
        open_action.setToolTip("Open file (Ctrl+O)")
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)

        # Save file
        self.save_action = QAction(
            QIcon(":/images/themes/default/mActionFileSave.svg"), "Save", self
        )
        self.save_action.setToolTip("Save file (Ctrl+S)")
        self.save_action.triggered.connect(self._save_file)
        toolbar.addAction(self.save_action)

        # Save As
        save_as_action = QAction(
            QIcon(":/images/themes/default/mActionFileSaveAs.svg"), "Save As", self
        )
        save_as_action.setToolTip("Save As (Ctrl+Shift+S)")
        save_as_action.triggered.connect(self._save_file_as)
        toolbar.addAction(save_as_action)

        # Comment/Uncomment
        comment_action = QAction(
            QIcon(":/images/themes/default/mActionFormAnnotation.svg"),
            "Comment/Uncomment",
            self,
        )
        comment_action.setToolTip("Comment/Uncomment selected lines (Ctrl+/)")
        comment_action.triggered.connect(self._toggle_comment)
        toolbar.addAction(comment_action)

        toolbar.addSeparator()

        # Run script
        run_action = QAction(
            QIcon(":/images/themes/default/mActionStart.svg"), "Run Script", self
        )
        run_action.setToolTip("Run entire script (F5 or Ctrl+R)")
        run_action.triggered.connect(self._run_script)
        toolbar.addAction(run_action)

        # Run selection
        run_sel_action = QAction(
            QIcon(":/images/themes/default/mActionArrowRight.svg"),
            "Run Selection",
            self,
        )
        run_sel_action.setToolTip("Run selected code (F9 or Ctrl+E)")
        run_sel_action.triggered.connect(self._run_selection)
        toolbar.addAction(run_sel_action)
        # Hide text to show only icon (consistent with other buttons)
        toolbar.widgetForAction(run_sel_action).setToolButtonStyle(
            Qt.ToolButtonIconOnly
        )

        # Clear output
        clear_action = QAction(
            QIcon(":/images/themes/default/console/iconClearConsole.svg"),
            "Clear Output",
            self,
        )
        clear_action.setToolTip("Clear output panel")
        clear_action.triggered.connect(self._clear_output)
        toolbar.addAction(clear_action)

        return toolbar

    def _setup_editor(self):
        """Set up and configure the Python code editor."""
        editor = QgsCodeEditorPython()

        # Line numbers
        editor.setLineNumbersVisible(True)

        # Code folding
        editor.setFoldingVisible(True)

        # Indentation
        editor.setIndentationsUseTabs(False)
        editor.setIndentationWidth(4)
        editor.setAutoIndent(True)

        # Margins
        editor.setMarginLineNumbers(0, True)
        editor.setMarginWidth(0, "00000")

        # Auto-completion
        editor.setAutoCompletionThreshold(2)

        # Connect text changed signal
        editor.textChanged.connect(self._on_text_changed)

        # Set initial template
        editor.setText(self._get_template_code())

        # Install event filter for keyboard shortcuts
        editor.installEventFilter(self)

        return editor

    def _setup_output_panel(self):
        """Set up the output panel for displaying execution results."""
        output = QTextEdit()
        output.setReadOnly(True)
        output.setPlaceholderText("Output will appear here...")
        return output

    def _get_template_code(self):
        """Return template code for new files."""
        return """# QGIS Python Editor
#
# Available objects:
#   iface    - QGIS interface
#   project  - Current project (QgsProject.instance())
#   canvas   - Map canvas
#   layers   - All map layers dictionary
#
# Example: List all layers
for layer_id, layer in layers.items():
    print(f"{layer.name()}: {layer_id}")
"""

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
        # File operations
        QShortcut(QKeySequence.New, self).activated.connect(self._new_file)
        QShortcut(QKeySequence.Open, self).activated.connect(self._open_file)
        QShortcut(QKeySequence.Save, self).activated.connect(self._save_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(
            self._save_file_as
        )

        # Execution
        QShortcut(QKeySequence("F5"), self).activated.connect(self._run_script)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._run_script)
        QShortcut(QKeySequence("F9"), self).activated.connect(self._run_selection)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._run_selection)

    def eventFilter(self, obj, event):
        """Event filter to catch keyboard shortcuts in the editor."""
        if obj == self.editor and event.type() == event.KeyPress:
            # Check for Ctrl+/ (comment toggle)
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Slash:
                self._toggle_comment()
                return True  # Event handled
        return super().eventFilter(obj, event)

    # File operations

    def _new_file(self):
        """Create a new file (clear editor)."""
        # Check for unsaved changes
        if not self._prompt_save_if_modified():
            return

        # Clear editor
        self.editor.setText(self._get_template_code())
        self.current_file_path = None
        self.is_modified = False

        # Update UI
        self._update_title()
        self._update_status("New file created")

    def _open_file(self):
        """Open a Python file using file dialog."""
        # Check for unsaved changes
        if not self._prompt_save_if_modified():
            return

        # Get last directory from settings
        last_dir = self.settings.value(
            f"{self.SETTINGS_PREFIX}last_directory", os.path.expanduser("~")
        )

        # Show file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Python File", last_dir, "Python Files (*.py);;All Files (*.*)"
        )

        if file_path:
            try:
                # Read file
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Set editor content
                self.editor.setText(content)
                self.current_file_path = file_path
                self.is_modified = False

                # Save directory for next time
                self.settings.setValue(
                    f"{self.SETTINGS_PREFIX}last_directory", os.path.dirname(file_path)
                )

                # Update UI
                self._update_title()
                self._update_status(f"Opened: {os.path.basename(file_path)}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def _save_file(self):
        """Save the current file."""
        if self.current_file_path is None:
            # No path yet, do Save As
            return self._save_file_as()

        try:
            # Get content
            content = self.editor.text()

            # Write file
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update state
            self.is_modified = False
            self._update_title()
            self._update_status(f"Saved: {os.path.basename(self.current_file_path)}")

            # Show success message
            self.iface.messageBar().pushSuccess("Leafmap", "File saved successfully")
            return True

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
            return False

    def _save_file_as(self):
        """Save file with a new name."""
        # Determine initial directory
        if self.current_file_path:
            initial_dir = os.path.dirname(self.current_file_path)
        else:
            initial_dir = self.settings.value(
                f"{self.SETTINGS_PREFIX}last_directory", os.path.expanduser("~")
            )

        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Python File",
            initial_dir,
            "Python Files (*.py);;All Files (*.*)",
        )

        if file_path:
            # Ensure .py extension
            if not file_path.endswith(".py"):
                file_path += ".py"

            try:
                # Write file
                content = self.editor.text()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Update state
                self.current_file_path = file_path
                self.is_modified = False

                # Save directory
                self.settings.setValue(
                    f"{self.SETTINGS_PREFIX}last_directory",
                    os.path.dirname(file_path),
                )

                # Update UI
                self._update_title()
                self._update_status(f"Saved as: {os.path.basename(file_path)}")

                self.iface.messageBar().pushSuccess(
                    "Leafmap", "File saved successfully"
                )
                return True

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
                return False

        return False

    def _prompt_save_if_modified(self):
        """Check for unsaved changes and prompt user.

        Returns:
            bool: True if safe to proceed (saved or discarded), False to cancel
        """
        if not self.is_modified:
            return True

        # Get file name for message
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
        else:
            file_name = "untitled.py"

        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"'{file_name}' has unsaved changes.\n\nDo you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if reply == QMessageBox.Save:
            return self._save_file()
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    # Code execution

    def _run_script(self):
        """Execute all code in the editor."""
        code = self.editor.text()
        if not code.strip():
            self._append_output("No code to execute.\n", is_error=False)
            return

        self._execute_code(code, is_selection=False)

    def _run_selection(self):
        """Execute only the selected code."""
        if not self.editor.hasSelectedText():
            self._append_output("No code selected.\n", is_error=True)
            return

        code = self.editor.selectedText()
        self._execute_code(code, is_selection=True)

    def _execute_code(self, code, is_selection=False):
        """Execute Python code with QGIS context and output capture.

        Args:
            code (str): Python code to execute
            is_selection (bool): Whether this is selected code or full script
        """
        # Prepare output capture
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            # Redirect output
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Build execution namespace
            exec_globals = self._build_execution_context()

            # Clear output (for full script only)
            if not is_selection:
                self._clear_output()

            # Show execution message
            label = "selection" if is_selection else "script"
            self._append_output(f"Executing {label}...\n", color="#00D4FF")

            # Execute the code
            exec(code, exec_globals)

            # Get captured output
            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()

            # Display output
            if stdout_text:
                self._append_output(stdout_text, is_error=False)

            if stderr_text:
                self._append_output(stderr_text, is_error=True)

            # Success message
            self._append_output(
                f"\n{label.capitalize()} executed successfully.\n", color="#00FF00"
            )
            self.status_label.setText("Execution completed")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")

            # Refresh map to show changes
            self.iface.mapCanvas().refresh()

        except Exception as e:
            # Display full traceback
            import traceback

            error_msg = traceback.format_exc()
            self._append_output(f"\nError:\n{error_msg}\n", is_error=True)
            self.status_label.setText("Execution failed")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")

        finally:
            # Always restore stdout/stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    def _build_execution_context(self):
        """Build namespace with QGIS objects for code execution.

        Returns:
            dict: Execution namespace with QGIS objects
        """
        context = {
            # QGIS Interface - main access point
            "iface": self.iface,
            # Project access
            "QgsProject": QgsProject,
            "project": QgsProject.instance(),
            # Map canvas
            "canvas": self.iface.mapCanvas(),
            # Layers dictionary (layer_id -> layer object)
            "layers": QgsProject.instance().mapLayers(),
            # Make qgis modules available
            "__builtins__": __builtins__,
        }

        return context

    # Code editing

    def _toggle_comment(self):
        """Toggle comment on selected lines or current line."""
        # Get selection or current line
        if self.editor.hasSelectedText():
            # Get selected line range
            line_from, index_from, line_to, index_to = self.editor.getSelection()
        else:
            # No selection, use current line
            line_from, index_from = self.editor.getCursorPosition()
            line_to = line_from

        # Check if all selected lines are commented
        all_commented = True
        for line_num in range(line_from, line_to + 1):
            line_text = self.editor.text(line_num)
            stripped = line_text.lstrip()
            if stripped and not stripped.startswith("#"):
                all_commented = False
                break

        # Begin undo action for grouping
        self.editor.beginUndoAction()

        # Toggle comments for each line
        for line_num in range(line_from, line_to + 1):
            line_text = self.editor.text(line_num)

            # Skip empty lines
            if not line_text.strip():
                continue

            if all_commented:
                # Uncomment: remove # and optional space
                stripped = line_text.lstrip()
                indent = line_text[: len(line_text) - len(stripped)]
                if stripped.startswith("# "):
                    new_text = indent + stripped[2:]
                elif stripped.startswith("#"):
                    new_text = indent + stripped[1:]
                else:
                    new_text = line_text
            else:
                # Comment: add # at start of content
                stripped = line_text.lstrip()
                indent = line_text[: len(line_text) - len(stripped)]
                new_text = indent + "# " + stripped

            # Replace the line
            self.editor.setSelection(line_num, 0, line_num, len(line_text))
            self.editor.replaceSelectedText(new_text)

        # End undo action
        self.editor.endUndoAction()

        # Restore cursor position
        if self.editor.hasSelectedText():
            # Restore selection
            self.editor.setSelection(
                line_from, 0, line_to, len(self.editor.text(line_to))
            )
        else:
            # Place cursor at original line
            self.editor.setCursorPosition(line_from, 0)

    # Helper methods

    def _on_text_changed(self):
        """Handle editor text change - mark as modified."""
        if not self.is_modified:
            self.is_modified = True
            self._update_title()

    def _update_title(self):
        """Update dock title with filename and modified indicator."""
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
        else:
            file_name = "untitled.py"

        # Add asterisk if modified
        if self.is_modified:
            file_name += " *"

        self.setWindowTitle(f"Python Editor - {file_name}")

        # Update file label (only if it exists - UI might not be fully initialized)
        if hasattr(self, "file_label") and self.file_label is not None:
            self.file_label.setText(file_name)

    def _update_status(self, message):
        """Update status bar message.

        Args:
            message (str): Status message to display
        """
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def _clear_output(self):
        """Clear the output panel."""
        self.output_panel.clear()

    def _append_output(self, text, is_error=False, color=None):
        """Append text to output panel with color formatting.

        Args:
            text (str): Text to append
            is_error (bool): If True, display in red
            color (str): Optional color name or hex code (e.g., 'red', '#FF0000')
        """
        cursor = self.output_panel.textCursor()
        cursor.movePosition(cursor.End)

        # Set text color with better contrast for dark themes
        if color:
            self.output_panel.setTextColor(QColor(color))
        elif is_error:
            self.output_panel.setTextColor(QColor("#FF5555"))  # Light red
        else:
            self.output_panel.setTextColor(
                QColor("#CCCCCC")
            )  # Light gray (works on dark backgrounds)

        # Append text
        self.output_panel.append(text.rstrip())

        # Reset to default light gray
        self.output_panel.setTextColor(QColor("#CCCCCC"))

        # Auto-scroll to bottom
        scrollbar = self.output_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """Handle dock widget close event."""
        # Check for unsaved changes
        if self.is_modified:
            if not self._prompt_save_if_modified():
                event.ignore()
                return

        event.accept()
