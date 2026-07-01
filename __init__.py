"""
CSV Prompt Loader - ComfyUI custom node (flat single-file version).

All node code lives directly in this __init__.py so ComfyUI can register the
node without any secondary import step. The old two-file layout
(__init__.py -> nodes.py via importlib) is collapsed here to remove every
possible failure point in the import chain. nodes.py is kept in the repo for
reference but is no longer imported.

CSV layout expected (no header row):
    column 1  ->  output filename  (used to name the saved image)
    column 2  ->  the prompt text  (fed to the sampler / CLIP encode)
Any further columns are ignored.
"""

import csv
import json
import re
from pathlib import Path


class CSVPromptLoader:
    """
    Reads one row at a time from a CSV file in a designated folder and returns
    the prompt (column 2) plus a sanitized filename (column 1).

    Wire the outputs like this:
      - prompt   -> the workflow's prompt / text input
      - filename -> the Save Image node's filename_prefix
                    (right-click the Save Image node -> "Convert filename_prefix
                    to input", then connect this output to it)

    In auto_increment mode each queue run advances to the next row and remembers
    its position between runs. Check total_rows to know how many times to queue.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "csv_folder":    ("STRING",  {"default": "csv_prompts", "multiline": False}),
                "csv_filename":  ("STRING",  {"default": "prompts.csv", "multiline": False}),
                "mode":          (["auto_increment", "fixed_index"],),
                "fixed_index":   ("INT",     {"default": 0, "min": 0, "max": 99999}),
                "reset_to_zero": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES  = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES  = ("prompt", "filename", "current_index", "total_rows")
    FUNCTION      = "load_prompt"
    CATEGORY      = "Finance YouTube Bot"

    def load_prompt(self, csv_folder, csv_filename, mode, fixed_index, reset_to_zero):
        folder   = self._resolve_folder(csv_folder)
        csv_path = folder / csv_filename
        rows     = self._read_rows(csv_path)

        if not rows:
            msg = f"No rows found in: {csv_path}"
            return (msg, "csv_error", 0, 0)

        # Per-file state so switching between CSV files preserves each counter
        state_path = folder / f".state_{csv_filename}.json"

        if mode == "fixed_index":
            idx = fixed_index % len(rows)
        else:                                        # auto_increment
            if reset_to_zero:
                idx = 0
            else:
                idx = self._read_state(state_path) % len(rows)
            # Save NEXT index so the following queue run advances
            self._write_state(state_path, (idx + 1) % len(rows))

        filename, prompt = rows[idx]
        return (prompt, filename, idx, len(rows))

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

    def _read_rows(self, csv_path: Path) -> list:
        """Return a list of (filename, prompt) tuples. No header row assumed."""
        if not csv_path.exists():
            return []
        rows = []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                # Need at least a prompt column; skip fully blank lines
                if not row or not any(cell.strip() for cell in row):
                    continue
                filename = row[0].strip() if len(row) >= 1 else ""
                prompt   = row[1].strip() if len(row) >= 2 else ""
                if not prompt:
                    continue
                rows.append((self._safe_filename(filename), prompt))
        return rows

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Strip characters that are illegal in filenames on Windows/Linux."""
        name = name.strip()
        if not name:
            return "output"
        # Drop any extension the CSV might include; Save Image adds its own
        name = re.sub(r"\.(png|jpg|jpeg|webp)$", "", name, flags=re.IGNORECASE)
        # Replace path separators and reserved characters with underscore
        name = re.sub(r'[\\/:*?"<>|]+', "_", name)
        name = name.strip(". ")
        return name or "output"

    def _read_state(self, path: Path) -> int:
        try:
            return json.loads(path.read_text()).get("idx", 0)
        except Exception:
            return 0

    def _write_state(self, path: Path, idx: int):
        path.write_text(json.dumps({"idx": idx}))


class SaveImageCSVFilename:
    """
    Saves images using an EXACT filename supplied on the `filename` input, with
    no auto-appended counter. Feed the CSVPromptLoader's `filename` output here.

    - Single image  -> <filename>.png
    - Batch of N     -> <filename>_01.png ... (suffix only added when N > 1)
    Existing files with the same name are overwritten (filenames come from your
    CSV column 1, so keep them unique). Files are always written inside the
    ComfyUI output directory (path separators in the name are stripped).
    """

    def __init__(self):
        import folder_paths
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images":   ("IMAGE",),
                "filename": ("STRING", {"default": "output", "forceInput": True}),
            },
            "optional": {
                "subfolder":     ("STRING",  {"default": "", "multiline": False}),
                "save_metadata": ("BOOLEAN", {"default": True}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION     = "save_images"
    OUTPUT_NODE  = True
    CATEGORY     = "Finance YouTube Bot"

    def save_images(self, images, filename, subfolder="", save_metadata=True,
                    prompt=None, extra_pnginfo=None):
        import os
        import json
        import numpy as np
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        base = CSVPromptLoader._safe_filename(filename)
        sub  = re.sub(r'[\\/:*?"<>|]+', "_", subfolder.strip()).strip("/ ")

        out_folder = os.path.join(self.output_dir, sub) if sub else self.output_dir
        os.makedirs(out_folder, exist_ok=True)

        batch = len(images)
        results = []
        for idx, image in enumerate(images):
            arr = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

            metadata = None
            if save_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key, val in extra_pnginfo.items():
                        metadata.add_text(key, json.dumps(val))

            name = f"{base}.png" if batch == 1 else f"{base}_{idx + 1:02d}.png"
            img.save(os.path.join(out_folder, name), pnginfo=metadata, compress_level=4)
            results.append({"filename": name, "subfolder": sub, "type": self.type})

        return {"ui": {"images": results}}


NODE_CLASS_MAPPINGS = {
    "CSVPromptLoader":     CSVPromptLoader,
    "SaveImageCSVFilename": SaveImageCSVFilename,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CSVPromptLoader":      "CSV Prompt Loader",
    "SaveImageCSVFilename": "Save Image (CSV filename)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
