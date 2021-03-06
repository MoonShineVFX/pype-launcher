
import os
import uuid
import copy
import getpass
import logging
import collections

from Qt import QtCore, QtGui
from avalon.vendor import qtawesome
from avalon import api, lib as avalon_lib

from . import lib
from .constants import (
    ACTION_ROLE,
    GROUP_ROLE,
    ACTION_ID_ROLE
)
from .actions import ApplicationAction
from .openpype import style

log = logging.getLogger(__name__)


class TaskModel(QtGui.QStandardItemModel):
    """A model listing the tasks combined for a list of assets"""

    def __init__(self, dbcon, parent=None):
        super(TaskModel, self).__init__(parent=parent)
        self.dbcon = dbcon

        self._num_assets = 0

        self.default_icon = qtawesome.icon(
            "fa.male", color=style.colors.default
        )
        self.no_task_icon = qtawesome.icon(
            "fa.exclamation-circle", color=style.colors.mid
        )

        self._icons = {}

        self._get_task_icons()

    def _get_task_icons(self):
        if not self.dbcon.Session.get("AVALON_PROJECT"):
            return

        # Get the project configured icons from database
        project = self.dbcon.find_one({"type": "project"})
        for task in project["config"].get("tasks") or []:
            icon_name = task.get("icon")
            if icon_name:
                self._icons[task["name"]] = qtawesome.icon(
                    "fa.{}".format(icon_name), color=style.colors.default
                )

    def set_assets(self, asset_ids=None, asset_docs=None):
        """Set assets to track by their database id

        Arguments:
            asset_ids (list): List of asset ids.
            asset_docs (list): List of asset entities from MongoDB.

        """

        if asset_docs is None and asset_ids is not None:
            # find assets in db by query
            asset_docs = list(self.dbcon.find({
                "type": "asset",
                "_id": {"$in": asset_ids}
            }))
            db_assets_ids = tuple(asset_doc["_id"] for asset_doc in asset_docs)

            # check if all assets were found
            not_found = tuple(
                str(asset_id)
                for asset_id in asset_ids
                if asset_id not in db_assets_ids
            )

            assert not not_found, "Assets not found by id: {0}".format(
                ", ".join(not_found)
            )

        self.clear()

        if not asset_docs:
            return

        task_names = set()
        for asset_doc in asset_docs:
            asset_tasks = asset_doc.get("data", {}).get("tasks") or set()
            task_names.update(asset_tasks)

        self.beginResetModel()

        if not task_names:
            item = QtGui.QStandardItem(self.no_task_icon, "No task")
            item.setEnabled(False)
            self.appendRow(item)

        else:
            for task_name in sorted(task_names):
                icon = self._icons.get(task_name, self.default_icon)
                item = QtGui.QStandardItem(icon, task_name)
                self.appendRow(item)

        self.endResetModel()

    def headerData(self, section, orientation, role):
        if (
            role == QtCore.Qt.DisplayRole
            and orientation == QtCore.Qt.Horizontal
            and section == 0
        ):
            return "Tasks"
        return super(TaskModel, self).headerData(section, orientation, role)


class ActionModel(QtGui.QStandardItemModel):
    def __init__(self, dbcon, parent=None):
        super(ActionModel, self).__init__(parent=parent)
        self.dbcon = dbcon

        self.default_icon = qtawesome.icon("fa.cube", color="white")
        # Cache of available actions
        self._registered_actions = list()
        self.items_by_id = {}

    def discover(self):
        """Set up Actions cache. Run this for each new project."""
        # Discover all registered actions
        actions = api.discover(api.Action)

        # Get available project actions and the application actions
        app_actions = self.get_application_actions() or []
        actions.extend(app_actions)

        self._registered_actions = actions
        self.items_by_id.clear()

    def get_application_actions(self):
        if not self.dbcon.Session.get("AVALON_PROJECT"):
            return

        project = self.dbcon.find_one({"type": "project"})
        if not project:
            return

        apps = []
        for app in project["config"]["apps"]:
            try:
                app_definition = avalon_lib.get_application(app['name'])
            except Exception as exc:
                print("Unable to load application: %s - %s" % (app['name'], exc))
                continue

            # Get from app definition, if not there from app in project
            icon = app_definition.get("icon", app.get("icon", "folder-o"))
            color = app_definition.get("color", app.get("color", None))
            order = app_definition.get("order", app.get("order", 0))
            label = app.get("label", app_definition.get("label", app["name"]))

            action = type(
                "app_%s" % app["name"],
                (ApplicationAction,),
                {
                    "name": app["name"],
                    "label": label,
                    "group": None,
                    "icon": icon,
                    "color": color,
                    "order": order,
                    "config": app_definition.copy(),
                }
            )

            apps.append(action)

        return apps

    def get_icon(self, action, skip_default=False):
        icon = lib.get_action_icon(action)
        if not icon and not skip_default:
            return self.default_icon
        return icon

    def filter_actions(self):
        # Validate actions based on compatibility
        self.clear()

        self.items_by_id.clear()

        actions = self.filter_compatible_actions(self._registered_actions)

        self.beginResetModel()

        single_actions = []
        grouped_actions = collections.defaultdict(list)
        for action in actions:
            # Groups
            group_name = getattr(action, "group", None)
            if group_name:
                grouped_actions[group_name].append(action)
            else:
                single_actions.append(action)

        items_by_order = collections.defaultdict(list)

        for action in single_actions:
            icon = self.get_icon(action)
            label = lib.get_action_label(action)
            item = QtGui.QStandardItem(icon, label)
            item.setData(label, QtCore.Qt.ToolTipRole)
            item.setData(action, ACTION_ROLE)
            items_by_order[action.order].append(item)

        for group_name, actions in grouped_actions.items():
            icon = None
            order = None
            for action in actions:
                if order is None or action.order < order:
                    order = action.order

                if icon is None:
                    _icon = lib.get_action_icon(action)
                    if _icon:
                        icon = _icon

            if icon is None:
                icon = self.default_icon

            item = QtGui.QStandardItem(icon, group_name)
            item.setData(actions, ACTION_ROLE)
            item.setData(True, GROUP_ROLE)

            items_by_order[order].append(item)

        for order in sorted(items_by_order.keys()):
            for item in items_by_order[order]:
                item_id = str(uuid.uuid4())
                item.setData(item_id, ACTION_ID_ROLE)
                self.items_by_id[item_id] = item
                self.appendRow(item)

        self.endResetModel()

    def filter_compatible_actions(self, actions):
        """Collect all actions which are compatible with the environment

        Each compatible action will be translated to a dictionary to ensure
        the action can be visualized in the launcher.

        Args:
            actions (list): list of classes

        Returns:
            list: collection of dictionaries sorted on order int he
        """

        compatible = []
        _session = copy.deepcopy(self.dbcon.Session)
        session = {
            key: value
            for key, value in _session.items()
            if value
        }

        for action in actions:
            if action().is_compatible(session):
                compatible.append(action)

        # Sort by order and name
        return sorted(
            compatible,
            key=lambda action: (action.order, action.name)
        )


class ProjectModel(QtGui.QStandardItemModel):
    """List of projects"""

    def __init__(self, dbcon, parent=None):
        super(ProjectModel, self).__init__(parent=parent)

        self.dbcon = dbcon

        self.hide_invisible = False
        self.project_icon = qtawesome.icon("fa.map", color="white")

    def refresh(self):
        self.clear()
        self.beginResetModel()

        for name in sorted(self.get_project_names()):
            item = QtGui.QStandardItem(self.project_icon, name)
            self.appendRow(item)

        self.endResetModel()

    def get_project_names(self):

        def project_visible(data):
            return self.hide_invisible and not data.get("visible", True)

        def project_member(data):
            user = getpass.getuser().lower()
            member = data.get("role", dict()).get("member", list())
            return user in member

        project_active = (project_member
                          if os.getenv("AVALON_LAUNCHER_USE_PROJECT_MEMBER")
                          else project_visible)

        projection = {"name": 1, "data.visible": 1, "data.role": 1}
        for project_doc in self.dbcon.projects(projection=projection):

            if project_active(project_doc["data"]):
                yield project_doc["name"]
