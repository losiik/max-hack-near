import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from max_assist.main import app  # noqa: E402

# openapi.yaml в корне нужен для DATA-API.yaml: по нему жюри сверяет пути проверок
if __name__ == "__main__":
    target = BASE_DIR.parent / "openapi.yaml"
    target.write_text(yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(target)
