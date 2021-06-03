"""Application entry-point"""

# Standard library
import os
import sys
from contextlib import contextmanager

# Dependencies
from avalon import io
from avalon.vendor import qtawesome
from Qt import QtCore, QtGui, QtWidgets

# Local libraries
from . import lib, window


ICON_PATH = lib.core_resource("icons", "png", "avalon-logo-16.png")
SPLASH_PATH = lib.core_resource("icons", "png", "splash.png")


@contextmanager
def fulfill_schema():
    # Fulfill schema [avalon-core:session-2.0], and expect the application
    # to fill it in in due course.
    _SESSION_STEPS = (
        "AVALON_PROJECTS",
        "AVALON_PROJECT",
        "AVALON_ASSET",
    )
    _PLACEHOLDER = "placeholder"

    for step in _SESSION_STEPS:
        if step not in os.environ:
            os.environ[step] = _PLACEHOLDER

    yield

    for step in _SESSION_STEPS:
        if os.environ[step] == _PLACEHOLDER:
            os.environ.pop(step)
            io.Session[step] = None


class Application(QtWidgets.QApplication):

    def __init__(self):
        super(Application, self).__init__(sys.argv)
        self.setWindowIcon(QtGui.QIcon(ICON_PATH))

        pixmap = QtGui.QPixmap(SPLASH_PATH)
        splash = QtWidgets.QSplashScreen(pixmap)
        splash.show()
        self._splash = splash
        self._splash.showMessage("Connecting database...",
                                 QtCore.Qt.AlignBottom, QtCore.Qt.black)

        with fulfill_schema():
            try:
                io.install()
            except IOError:
                raise  # Server refused to connect

        # Install actions
        from . import install
        install()

        self._splash.showMessage("Starting Avalon Launcher...",
                                 QtCore.Qt.AlignBottom, QtCore.Qt.black)

        self._tray = None
        self.window = None

        self.setQuitOnLastWindowClosed(False)

    def init_tray(self):

        tray = QtWidgets.QSystemTrayIcon(self.windowIcon(), parent=self)
        tray.setToolTip("Avalon Launcher")

        # Build the right-mouse context menu for the tray icon
        menu = QtWidgets.QMenu()

        def window_show():
            self.window.show()
            self.window.raise_()
            self.window.requestActivate()

        show = QtWidgets.QAction("Show", self)
        show.triggered.connect(window_show)
        menu.addAction(show)

        def on_quit():
            # fix crash on quit with QML window open
            self.closeAllWindows()

            # fix tray icon remaining visible until hover over
            self._tray.hide()

            self.quit()

        quit = QtWidgets.QAction("Quit", self)
        quit.triggered.connect(on_quit)
        menu.addAction(quit)
        tray.setContextMenu(menu)

        # Add the double clicked behavior
        def on_tray_activated(reason):
            if reason == QtWidgets.QSystemTrayIcon.Context:
                return

            if self.window.isVisible():
                self.window.hide()

            elif reason == QtWidgets.QSystemTrayIcon.Trigger:
                window_show()

        tray.activated.connect(on_tray_activated)

        self._tray = tray

        tray.show()
        tray.showMessage("Avalon",
                         "Launcher tray started.",
                         qtawesome.icon("fa.info", color="#9A9A9A"),
                         500)

        self._splash.close()


def main():
    print("Starting avalon-launcher")
    app = Application()

    app.window = window.LauncherWindow()
    app.init_tray()
    app.window.show()

    # Set current project by default if it's set.
    project_name = app.window.dbcon.Session.get("AVALON_PROJECT")
    if project_name:
        app.window.on_project_clicked(project_name)

    return app.exec_()
