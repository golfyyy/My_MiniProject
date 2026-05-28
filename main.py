import asyncio
import os
import sys
import logging
from core.logging_setup import setup_logging
from core.engine import GoldAIEngine

# Reconfigure stdout for UTF-8 compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Setup logging with RotatingFileHandler
project_root: str = os.path.dirname(os.path.abspath(__file__))
setup_logging(project_root)
logger = logging.getLogger("GoldAI.Main")


async def main() -> None:
    engine = GoldAIEngine()
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    def shutdown_handler(sig, frame) -> None:
        logger.info(f"Received shutdown signal ({sig}). Initiating graceful shutdown...")
        if main_task:
            loop.call_soon_threadsafe(main_task.cancel)

    import signal
    try:
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)
    except ValueError:
        pass

    try:
        await engine.main_loop()
    except asyncio.CancelledError:
        logger.info("Main engine task cancelled for graceful shutdown.")
    finally:
        logger.info("Graceful shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
