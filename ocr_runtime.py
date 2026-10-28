"""A private, per-user OCR interpreter; independent of the app's Python."""
import os
from pathlib import Path


def environment_path():
    base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')
    return base/'Engelmig'/'ocr-python312'


def python_path():
    return environment_path()/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
