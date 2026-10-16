A Python virtual environment is an isolated folder with its own Python interpreter and installed packages, so each project can keep its own dependency versions without touching the system Python or other projects.

Create and use one with the built-in `venv` module:

```bash
python3 -m venv .venv            # create it in the project folder
source .venv/bin/activate        # activate on macOS/Linux
.venv\Scripts\activate           # activate on Windows
pip install requests             # installs into .venv only
pip freeze > requirements.txt    # record dependencies
deactivate                       # leave the environment
```

Once it's active, `python` and `pip` point to the environment's copies. Your shell prompt usually shows `(.venv)` while it's on.

The most common mistake is forgetting to activate it. `pip install` then puts packages in the global Python, and your project can't find them. Add `.venv/` to `.gitignore`, because the folder belongs to one machine and should be rebuilt from `requirements.txt` instead of committed.