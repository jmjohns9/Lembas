A virtual environment is a directory with its own Python interpreter link and its own `site-packages`. Packages you install while it is active go into that directory, not the system Python, so each project keeps its own dependency versions without clashing with the others.

```bash
python3 -m venv .venv            # create it in the project folder
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install requests             # installs into .venv only
pip freeze > requirements.txt    # record versions
deactivate                       # leave the environment
```

Use one for every project. Use the system Python only for one-off scripts that need just the standard library. `uv venv` creates the same kind of environment and runs faster.

Common mistakes:

- **Committing `.venv`:** add it to `.gitignore` and rebuild it with `pip install -r requirements.txt`.
- **Moving or renaming the folder:** a venv stores absolute paths, so it breaks. Recreate it instead.
- **Debian or Ubuntu:** you may need `sudo apt install python3-venv` before `python3 -m venv` will work.