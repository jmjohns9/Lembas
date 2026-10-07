A Python virtual environment is a self-contained folder that holds its own Python interpreter and its own set of installed packages, separate from the Python installed on your system.

## Why use one

Without one, every `pip install` goes into a single global location. That causes problems quickly:

- **Version conflicts.** Project A needs pandas 1.5, Project B needs pandas 2.2. Globally, you can only have one.
- **Reproducibility.** A venv lets you capture exactly what a project needs in a `requirements.txt` so someone else (or a server) can rebuild it.
- **Clean system Python.** You avoid breaking OS tools that depend on the system Python, and you usually don't need admin rights to install packages.

Think of it as one isolated sandbox per project.

## How to create one

Python 3.3+ includes the `venv` module, so there's nothing extra to install.

**1. Create it** (from your project folder):

```bash
python -m venv .venv
```

This creates a `.venv` folder. The name is up to you, but `.venv` is a common convention and most editors detect it automatically. On some systems you'll need `python3` instead of `python`.

**2. Activate it:**

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Your prompt will show `(.venv)` once it's active. Now `python` and `pip` point to the environment, not the system install.

**3. Install packages:**

```bash
pip install pandas requests
```

These land only inside `.venv`.

**4. Save your dependencies:**

```bash
pip freeze > requirements.txt
```

Anyone can then recreate the environment with:

```bash
pip install -r requirements.txt
```

**5. Deactivate when done:**

```bash
deactivate
```

## A few practical tips

- **Don't commit the venv folder.** Add `.venv/` to your `.gitignore` and commit `requirements.txt` instead.
- **Don't move or rename it.** Venvs contain hardcoded paths. If you need it somewhere else, delete it and recreate it.
- **PowerShell blocked the activate script?** Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **VS Code** will usually prompt you to select the `.venv` interpreter. If not, use "Python: Select Interpreter" from the command palette.
- **Want something faster?** `uv` is a newer tool that does the same thing much faster (`uv venv`, then `uv pip install ...`). Plain `venv` is still perfectly fine and works everywhere.
