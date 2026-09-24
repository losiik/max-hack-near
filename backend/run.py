import os
import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"

os.chdir(BASE_DIR)
sys.path.insert(0, str(SRC_DIR))
os.environ["PYTHONPATH"] = str(SRC_DIR)

if __name__ == "__main__":
    command.upgrade(Config("alembic.ini"), "head")
    uvicorn.run("max_assist.main:app", reload=True, reload_dirs=[str(SRC_DIR)])
