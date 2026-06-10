"""
CSV Prompt Loader - ComfyUI custom node (flat single-file version).

All node code lives directly in this __init__.py so ComfyUI can register the
node without any secondary import step. The old two-file layout
(__init__.py -> nodes.py via importlib) is collapsed here to remove every
possible failure point in the import chain. nodes.py is kept in the repo for
reference but is no longer imported.
"""

import csv
import json
from pathlib import Path


class CSVPromptLoader:
    """
    Reads prompts one at a time from a single CSV file in a designated folder.
    Switch csv_filename between part1/part2/part3 manually between sessions.
    Check the total_prompts output to know how many times to queue.

    Designed for the Finance YouTube Bot 3-part CSV output:
      csv_prompts/prompts_YYYY-MM-DD_part1.csv  (80 prompts)
      csv_prompts/prompts_YYYY-MM-DD_part2.csv  (80 prompts)
      csv_prompts/prompts_YYYY-MM-DD_part3.csv  (90 prompts)
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "csv_folder":    ("STRING",  {"default": "csv_prompts", "multiline": False}),
                "csv_filename":  ("STRING",  {"default": "part1.csv",   "multiline": False}),
                "mode":          (["auto_increment", "fixed_index"],),
                "fixed_index":   ("INT",     {"default": 0, "min": 0, "max": 99999}),
                "reset_to_zero": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES  = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES  = ("positive_prompt", "negative_prompt", "current_index", "total_prompts")
    FUNCTION      = "load_prompt"
    CATEGORY      = "Finance YouTube Bot"

    def load_prompt(self, csv_folder, csv_filename, mode, fixed_index, reset_to_zero):
        folder   = self._resolve_folder(csv_folder)
        csv_path = folder / csv_filename
        prompts  = self._read_prompts(csv_path)

        if not prompts:
            msg = f"No prompts found in: {csv_path}"
            return (msg, "", 0, 0)

        # Per-file state so switching between part1/part2/part3 preserves each counter
        state_path = folder / f".state_{csv_filename}.json"

        if mode == "fixed_index":
            idx = fixed_index % len(prompts)
        else:                                        # auto_increment
            if reset_to_zero:
                idx = 0
            else:
                idx = self._read_state(state_path)
            # Save NEXT index so the following queue run advances
            self._write_state(state_path, (idx + 1) % len(prompts))

        raw = prompts[idx]

        # Split positive / negative at the suffix the Finance bot appends
        if "\nnegative:" in raw:
            pos, neg = raw.split("\nnegative:", 1)
            pos, neg = pos.strip(), neg.strip()
        else:
            pos, neg = raw.strip(), ""

        return (pos, neg, idx, len(prompts))

    @classmethod
    def IS_CHANGED(cls, csv_folder, csv_filename, mode, fixed_index, reset_to_zero):
        # Return NaN to force re-execution on every queue run in auto_increment mode
        if mode == "auto_increment" or reset_to_zero:
            return float("nan")
        return fixed_index

    # ------------------------------------------------------------------ #

    def _resolve_folder(self, folder_name: str) -> Path:
        p = Path(folder_name)
        if p.is_absolute() and p.exists():
            return p
        # Walk up two levels: custom_nodes/<package>/__init__.py -> ComfyUI root
        comfyui_root = Path(__file__).parent.parent.parent
        resolved = comfyui_root / folder_name
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def _read_prompts(self, csv_path: Path) -> list:
        if not csv_path.exists():
            return []
        prompts = []
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if row and row[0].strip():
                    prompts.append(row[0].strip())
        return prompts

    def _read_state(self, path: Path) -> int:
        try:
            return json.loads(path.read_text()).get("idx", 0)
        except Exception:
            return 0

    def _write_state(self, path: Path, idx: int):
        path.write_text(json.dumps({"idx": idx}))


NODE_CLASS_MAPPINGS        = {"CSVPromptLoader": CSVPromptLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"CSVPromptLoader": "CSV Prompt Loader"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
