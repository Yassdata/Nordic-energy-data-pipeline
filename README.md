# Nordic Energy Data Pipeline

A learning project for extracting Danish day-ahead electricity prices for DK1
and DK2 from Energi Data Service, checking data quality, and preparing data for
analysis.

## Project layout

```text
scripts/
  api_data_extraction.ipynb     # API extraction and data quality checks
  data_preparation.ipynb        # Prepare timestamps and write Parquet safely
json_data_file/
  prices.json                   # Existing source snapshot, kept locally
data/processed/
  day_ahead_prices.parquet       # Existing processed dataset, kept locally
.vscode/                        # Settings for this project only
requirements.txt                # Direct Python dependencies
```

Existing files retain their original names and locations. Downloaded JSON and
generated data are ignored by Git; ignoring them does not delete them. A fresh
clone will not include these local datasets.

## Python setup

This project uses Python 3.12.3 in `.venv`. Global Python installations and shell
configuration are unchanged. An interrupted installation caused by low disk
space was repaired after space was freed.

For a new checkout, create and activate an environment, then install dependencies:

```zsh
cd "/Users/yassinehouari/Desktop/Nordic Energy Data Pipeline"
# Only create the environment if .venv does not already exist:
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m ipykernel install --sys-prefix --name nordic-energy --display-name "Nordic Energy (.venv)"
```

The absolute Python path above is specific to this Mac. On another computer,
use the path to an installed Python 3.12 interpreter instead.

Dependencies are limited to `requests` for API access, `pandas` for tabular data,
`pyarrow` for Parquet, and `ipykernel` for notebook execution. Direct versions
are pinned to the verified installation; transitive dependencies are resolved
by pip. No Jupyter server or JupyterLab installation is needed for VS Code.
Both notebooks' imports are covered by these four direct dependencies.

## VS Code and notebooks

Open this project folder itself with File → Open Folder. Workspace settings make
new terminals start here using zsh and set `.venv/bin/python` as the default
Python interpreter. Existing terminal sessions are not changed.

Use Command Palette → Python: Select Interpreter
and select `.venv/bin/python` if a different interpreter was previously saved.
In each notebook, use Select Kernel → Python Environments → the project's
`.venv`. Check the kernel by running:

```python
import sys
print(sys.executable)
```

The path should end in `Nordic Energy Data Pipeline/.venv/bin/python`.
VS Code's notebook working directory is configured to the project root, so
existing relative paths such as `json_data_file/prices.json` resolve from here.

Both notebooks now resolve their paths from either the project root
or `scripts/`. The extraction notebook loads the existing JSON snapshot by default. If the snapshot
is missing, it calls the API and creates the JSON with exclusive creation mode,
which prevents replacing an existing file. To fetch another period deliberately,
call `get_day_ahead_prices(start_date, end_date)` and save the returned data under
a new filename.

The preparation notebook prepares the data in memory on every run and writes
the Parquet only if it does not already exist. Use a new output filename to
keep a fresh export alongside the existing dataset.

## Verification on 13 November 2026

- All dependencies imported successfully and `python -m pip check` passed.
- The project-local `Nordic Energy (.venv)` kernel was installed and successfully
  used for the extraction checks. A later live-kernel startup attempt timed out
  after 60 seconds while macOS continued offloading environment files.
  Reliable startup still requires keeping the folder downloaded locally.
- All 14 extraction notebook cells ran in that kernel from both the root and
  `scripts/`, using the saved snapshot with network requests blocked.
- All existing quality checks passed for 1,344 JSON records.
- The processed Parquet loaded successfully: 1,344 rows and 6 columns.
- JSON and Parquet SHA-256 hashes matched the originals after verification.
- All 4 preparation notebook code cells ran with `.venv` from both folders.
  The resulting DataFrame matched the original Parquet (ignoring dtype precision).
  The existing processed file was preserved.

Both original notebooks were backed up before editing under
`/tmp/nordic-energy-setup-originals/scripts/`.
That is a temporary backup, not a permanent version history.

macOS repeatedly marked files here, including environment files, as `dataless`.
Use Finder's Keep Downloaded option if available to keep the entire project local
while developing. Offloaded files can make Python imports and kernel startup slow.
Only offloaded, regenerable `.venv` bytecode caches were cleared during diagnosis;
no project source or datasets were deleted.

## Terminal basics

```zsh
pwd                         # Show the current directory
ls -la                      # List files, including hidden files
source .venv/bin/activate   # Use this project's Python in this terminal
python --version            # Check the active Python version
python -m pip --version     # Check pip for that same Python
python -m pip check         # Check installed dependency compatibility
deactivate                  # Leave the virtual environment
```

Use `python -m pip` after activation so installation uses the same interpreter
as your code. This Mac's global `python3` and `pip` currently resolve to different
Python installations. No global shell settings were changed.

## Learning Git manually

A local repository has been initialized. There are no commits or remotes, and
Git name and email were not changed. These commands only inspect your work:

```zsh
git status                  # Show untracked and modified files
git diff                    # Show edits to already tracked files
git diff --staged            # Show changes staged for the next commit
git check-ignore -v json_data_file/prices.json
```

`git diff` does not show the contents of untracked files. When you are ready,
practice `git add <file>` to stage a chosen file and `git commit` to record staged
changes yourself. No staging, commits, or GitHub operations were automated.
