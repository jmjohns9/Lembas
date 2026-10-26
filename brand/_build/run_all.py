"""Rebuild every brand asset in dependency order."""
import runpy

for script in ("concepts", "logo", "icons", "banners", "guidelines", "review", "overview", "kit"):
    runpy.run_path(f"{script}.py", run_name="__main__")
