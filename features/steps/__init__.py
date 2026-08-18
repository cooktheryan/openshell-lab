import glob
import importlib
import os


_steps_dir = os.path.dirname(__file__)
_package_name = "features.steps"
for _subdir in ("given", "when", "then"):
    _subdir_path = os.path.join(_steps_dir, _subdir)
    if not os.path.isdir(_subdir_path):
        continue
    importlib.import_module(f"{_package_name}.{_subdir}")
    for _filepath in sorted(glob.glob(os.path.join(_subdir_path, "*.py"))):
        _basename = os.path.basename(_filepath)
        if _basename.startswith("_"):
            continue
        _module_name = f"{_package_name}.{_subdir}.{_basename[:-3]}"
        importlib.import_module(_module_name)
