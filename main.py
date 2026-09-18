import asyncio
import sys

from app.bot import run_polling, setup_logging
from app.config import ConfigError, load_settings


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Sozlamada xatolik: {exc}. .env faylini tekshiring (.env.example ga qarang).", file=sys.stderr)
        sys.exit(1)

    setup_logging(settings)
    try:
        asyncio.run(run_polling(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
