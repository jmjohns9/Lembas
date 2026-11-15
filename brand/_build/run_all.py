"""Rebuild every brand asset in dependency order. Works from any folder."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)   # the scripts import lib and logo from this folder

for script in ("concepts", "logo", "icons", "banners", "guidelines", "review", "overview", "kit"):
    runpy.run_path(os.path.join(HERE, f"{script}.py"), run_name="__main__")
