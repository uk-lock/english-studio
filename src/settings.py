"""config/settings.toml と config/settings.local.toml を読み込む。"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def load_settings() -> dict:
    """共有設定に個人設定（秘密情報）をセクション単位で上書きマージして返す。"""
    settings: dict = {}
    for name in ("settings.toml", "settings.local.toml"):
        path = CONFIG_DIR / name
        if not path.exists():
            continue
        with path.open("rb") as f:
            for section, values in tomllib.load(f).items():
                if isinstance(values, dict):
                    settings.setdefault(section, {}).update(values)
                else:
                    settings[section] = values
    return settings


def database_url() -> str:
    """SQLAlchemy用の接続URL（psycopg3ドライバ指定）を返す。"""
    url = load_settings().get("db", {}).get("connection_string")
    if not url:
        raise RuntimeError("config/settings.local.toml の [db] connection_string が未設定です")
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url
