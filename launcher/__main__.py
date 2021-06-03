
import os
import sys
import importlib


EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def cli():
    # Check environment dependencies
    missing = []
    for dependency in ["AVALON_CONFIG", "AVALON_PROJECTS"]:
        if dependency not in os.environ:
            missing.append(dependency)
    if missing:
        sys.stderr.write(
            "Incomplete environment, missing variables:\n%s"
            % "\n".join("- %s" % var for var in missing)
        )

        return EXIT_FAILURE

    # Check modules dependencies
    missing = list()
    dependencies = {
        "PyQt5": None,
        "avalon": None,
        os.environ["AVALON_CONFIG"]: None
    }

    for dependency in dependencies:
        try:
            dependencies[dependency] = importlib.import_module(dependency)
        except ImportError as e:
            missing.append([dependency, e])

    if missing:
        missing_formatted = []
        for dep, error in missing:
            missing_formatted.append(
                "- \"{0}\"\n  Error: {1}".format(dep, error)
            )

        sys.stderr.write(
            "Missing modules:\n{0}\nPlease check your PYTHONPATH:\n{1}".format(
                "\n".join(missing_formatted),
                os.environ["PYTHONPATH"]
            )
        )

        return EXIT_FAILURE

    print("Using Python @ '%s'" % sys.executable)
    print("Using config: '%s'" % os.environ["AVALON_CONFIG"])

    dependencies["launcher"] = sys.modules[__name__]
    for dependency, lib in dependencies.items():
        print("Using {0} @ '{1}'".format(
            dependency, os.path.dirname(lib.__file__))
        )

    return show()


def show():
    from Qt import QtWidgets
    from . import install
    from .window import LauncherWindow

    install()

    app = QtWidgets.QApplication()
    window = LauncherWindow()
    window.show()

    return app.exec_()


sys.exit(cli())
