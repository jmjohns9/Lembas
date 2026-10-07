A virtual environment is a self-contained folder with its own Python interpreter and installed packages, so each project keeps its own dependency versions without touching the system Python or other projects.

Create and activate one with the built-in `venv` module:

```bash
python3 -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Once it's active, `pip install` puts packages only in `.venv`. Run `deactivate` to leave it.

Save your dependencies with `pip freeze > requirements.txt` so others can rebuild the environment with `pip install -r requirements.txt`. Add `.venv/` to `.gitignore`, because the folder is machine-specific and should not be committed.
