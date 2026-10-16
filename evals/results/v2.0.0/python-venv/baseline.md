A **Python virtual environment** is a self-contained folder with its own Python interpreter and its own set of installed packages. Packages you install while it's active go into that folder, not into your system-wide Python.

## Why use one

- **Each project keeps its own dependencies.** Project A can use `requests 2.28` while Project B uses `requests 2.32`, and neither breaks the other.
- **Your system Python stays clean.** Many operating systems rely on their own Python install, and installing packages into it can break things. Some Linux distros now block it outright (the "externally-managed-environment" error).
- **Builds are reproducible.** You can record exactly which packages a project needs and recreate the same setup on another machine.

## Creating one with the built-in `venv` module

Python 3.3 and later include `venv`, so you don't need to install anything.

```bash
# 1. Create the environment (".venv" is a common folder name)
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows (cmd)
.venv\Scripts\Activate.ps1       # Windows (PowerShell)

# 3. Install packages: they go into .venv only
pip install requests

# 4. Save your dependencies
pip freeze > requirements.txt

# 5. Leave the environment when you're done
deactivate
```

When the environment is active, your shell prompt usually shows `(.venv)`, and `python` and `pip` point to the copies inside `.venv`.

## Recreating it elsewhere

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tips

- **Don't commit the venv folder to git.** Add `.venv/` to `.gitignore` and commit `requirements.txt` (or `pyproject.toml`) instead.
- **You don't have to activate it.** You can call the environment's interpreter directly, e.g. `.venv/bin/python script.py`.
- **Faster alternative:** [`uv`](https://docs.astral.sh/uv/) does the same job much faster (`uv venv`, then `uv pip install ...`). Other options are `poetry`, `pipenv` and `conda`, which also manage dependencies and, in conda's case, non-Python packages.
- **Moving or renaming a venv breaks it**, because the paths inside it are hard-coded. Delete it and create it again instead.