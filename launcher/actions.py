import os
import importlib
import subprocess
from Qt import QtWidgets, QtGui
from avalon import api, lib
from .openpype import style, resources
from .openpype.lib.log import PypeLogger as Logger


def register_config_actions():
    """Register actions from the configuration for Launcher"""

    module_name = os.environ["AVALON_CONFIG"]
    config = importlib.import_module(module_name)
    if not hasattr(config, "register_launcher_actions"):
        print("Current configuration `%s` has no 'register_launcher_actions'"
              % config.__name__)
        return

    config.register_launcher_actions()


def register_environment_actions():
    """Register actions from AVALON_ACTIONS for Launcher."""

    paths = os.environ.get("AVALON_ACTIONS")
    if not paths:
        return

    for path in paths.split(os.pathsep):
        api.register_plugin_path(api.Action, path)

        # Run "register" if found.
        for module in lib.modules_from_path(path):
            if "register" not in dir(module):
                continue

            try:
                module.register()
            except Exception as e:
                print(
                    "Register method in {0} failed: {1}".format(
                        module, str(e)
                    )
                )


class ApplicationAction(api.Application):
    """Pype's application launcher

    Application action based on pype's ApplicationManager system.
    """

    # Action attributes
    name = None
    label = None
    group = None
    icon = None
    color = None
    order = 0

    _log = None

    @property
    def log(self):
        if self._log is None:
            self._log = Logger().get_logger(self.__class__.__name__)
        return self._log

    def _show_message_box(self, title, message, details=None):
        dialog = QtWidgets.QMessageBox()
        icon = QtGui.QIcon(resources.pype_icon_filepath())
        dialog.setWindowIcon(icon)
        dialog.setStyleSheet(style.load_stylesheet())
        dialog.setWindowTitle(title)
        dialog.setText(message)
        if details:
            dialog.setDetailedText(details)
        dialog.exec_()

    def launch(self, environment):
        try:
            super(ApplicationAction, self).launch(environment)

        except ValueError:
            msg = "'%s' not found in PATH :" % self.config["executable"]
            details = "\n    ".join(
                [p for p in os.environ["PATH"].split(os.pathsep) if p.strip()]
            )

            log_msg = str(msg)
            log_msg += "\n" + details
            self.log.warning(log_msg)
            self._show_message_box(
                "Application executable not found", msg, details
            )

        except subprocess.CalledProcessError as exc:
            msg = str(exc)
            self.log.warning(msg, exc_info=True)
            self._show_message_box("Application launch failed", msg)


class ProjectManagerAction(api.Action):
    name = "projectmanager"
    label = "Project Manager"
    icon = "gear"
    order = 999     # at the end

    def is_compatible(self, session):
        return "AVALON_PROJECT" in session

    def process(self, session, **kwargs):
        return lib.launch(executable="python",
                          args=["-u", "-m", "avalon.tools.projectmanager",
                                session['AVALON_PROJECT']])


class LoaderAction(api.Action):
    name = "loader"
    label = "Loader"
    icon = "cloud-download"
    order = 998     # at the end

    def is_compatible(self, session):
        return "AVALON_PROJECT" in session

    def process(self, session, **kwargs):
        return lib.launch(executable="python",
                          args=["-u", "-m", "avalon.tools.loader",
                                session['AVALON_PROJECT']])


def register_default_actions():
    """Register default actions for Launcher"""
    api.register_plugin(api.Action, ProjectManagerAction)
    api.register_plugin(api.Action, LoaderAction)
