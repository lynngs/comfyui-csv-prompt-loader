# ComfyUI CSV Prompt Loader

Two ComfyUI custom nodes for batch image generation driven by a CSV file:

- **CSV Prompt Loader** — reads one row per queue run and outputs the prompt and a filename.
- **Save Image (CSV filename)** — saves the image under that exact filename, with **no** `_00001_` counter appended.

Built for feeding a list of prompts (e.g. a Flux.2 Klein image-edit workflow) where each output image should be named from the CSV.

---

## Installation

### RunPod / Linux (Jupyter terminal)

```bash
cd /workspace/ComfyUI/custom_nodes          # adjust if your path is /ComfyUI
git clone https://github.com/lynngs/comfyui-csv-prompt-loader.git
```

To update later:

```bash
cd /workspace/ComfyUI/custom_nodes/comfyui-csv-prompt-loader
git pull
```

Then **restart ComfyUI** so the nodes register. No extra Python packages are
needed — the save node uses `numpy` and `Pillow`, which ship with ComfyUI.

### Local

Clone (or copy) this folder into `ComfyUI/custom_nodes/` and restart ComfyUI.

---

## CSV format

No header row. **Column 1 = output filename, Column 2 = prompt.** Any further
columns are ignored. Standard CSV quoting applies, so prompts containing commas
must be wrapped in double quotes.

```csv
market_scene,"A stick figure at a busy market stall, teal glasses, orange dress"
courtroom_shield,"Stick figure in a courtroom holding a large shield emblem"
office_desk,"Stick figure sitting at a desk reviewing documents"
```

Place the file inside a folder at the ComfyUI root, e.g.
`ComfyUI/csv_prompts/prompts.csv`.

Column 1 is sanitized into a safe filename automatically: any file extension is
dropped (the save node adds `.png`), and the characters `\ / : * ? " < > |` are
replaced with `_`. So `street/market:scene.png` becomes `street_market_scene`.

---

## Nodes

### CSV Prompt Loader

*Category: Finance YouTube Bot*

| Input | Default | Description |
|---|---|---|
| `csv_folder` | `csv_prompts` | Folder (relative to the ComfyUI root, or an absolute path) holding the CSV. |
| `csv_filename` | `prompts.csv` | The CSV file to read. |
| `mode` | `auto_increment` | `auto_increment` advances one row per queue run; `fixed_index` reads a specific row. |
| `fixed_index` | `0` | Row number to read when `mode = fixed_index`. |
| `reset_to_zero` | `false` | In `auto_increment`, set to `true` for one run to restart at row 0. |

| Output | Description |
|---|---|
| `prompt` | Column 2 of the current row. |
| `filename` | Column 1 of the current row, sanitized. |
| `current_index` | The row number just read (0-based). |
| `total_rows` | Number of usable rows — tells you how many times to queue. |

In `auto_increment` mode the current position is stored per-file in a hidden
`.state_<filename>.json` beside the CSV, so it resumes where it left off across
sessions. It wraps back to row 0 after the last row.

### Save Image (CSV filename)

*Category: Finance YouTube Bot*

| Input | Default | Description |
|---|---|---|
| `images` | — | Images to save. |
| `filename` | — | Exact filename to use (connect the loader's `filename` output). |
| `subfolder` | `""` | Optional subfolder under the ComfyUI `output/` directory. |
| `save_metadata` | `true` | Embed the workflow/prompt in the PNG so it can be dragged back into ComfyUI. |

Saves `<filename>.png` in the ComfyUI output directory — no counter suffix. A
batch of more than one image gets `_01`, `_02`, … suffixes. Files with the same
name are overwritten, so keep column-1 values unique.

---

## Usage

1. In ComfyUI, load `example_workflow/image_flux2_klein_csv_loader.json` (or wire
   the nodes into your own workflow).
2. On the **CSV Prompt Loader** node, set `csv_folder` and `csv_filename`.
3. Wire it up:
   - `prompt` → your workflow's prompt / text input
   - your workflow's `IMAGE` output → **Save Image (CSV filename)** `images`
   - `filename` → **Save Image (CSV filename)** `filename`
4. Set `reset_to_zero = true` for the first queue to start at row 0, then set it
   back to `false`. Check `total_rows` to know how many times to queue.

The included example workflow is a Flux.2 Klein 9B image-edit graph already wired
this way; its old built-in `SaveImage` node is muted so it won't double-save.
