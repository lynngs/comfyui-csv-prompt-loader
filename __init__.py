import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "csv_prompt_loader_nodes",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "nodes.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

NODE_CLASS_MAPPINGS        = _mod.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = _mod.NODE_DISPLAY_NAME_MAPPINGS
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
