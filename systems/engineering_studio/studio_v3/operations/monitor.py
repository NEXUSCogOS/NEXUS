"""Continuous monitoring and autonomous repair loop"""
import time
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

class StudioMonitor:
    def __init__(self, config_path: str, repo_path: str, interval_seconds: int = 300):
        self.config_path = config_path
        self.repo_path = repo_path
        self.interval = interval_seconds
        self.setup_logging()

    def setup_logging(self):
        log_dir = Path(self.repo_path) / '.studio_logs'
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f'studio_{datetime.now(timezone.utc).isoformat()}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def run_continuous(self, max_cycles: int = None):
        """Run autonomous repair loop continuously"""
        from .controller import StudioController

        controller = StudioController(self.config_path, self.repo_path)
        cycle = 0

        self.logger.info("Studio monitor started - continuous autonomous repair enabled")

        while max_cycles is None or cycle < max_cycles:
            cycle += 1
            self.logger.info(f"Cycle {cycle} starting...")

            try:
                results = controller.run_repair_loop()

                if results.get('findings'):
                    self.logger.info(f"Found {len(results['findings'])} issues")
                if results.get('tasks_executed'):
                    self.logger.info(f"Executed {len(results['tasks_executed'])} repairs")
                if results.get('failures'):
                    self.logger.warning(f"{len(results['failures'])} repairs failed")
                if results.get('error'):
                    self.logger.error(f"Cycle error: {results['error']}")
                else:
                    self.logger.info("Cycle completed successfully")

            except Exception as e:
                self.logger.error(f"Cycle exception: {e}", exc_info=True)

            if max_cycles is None or cycle < max_cycles:
                self.logger.info(f"Next cycle in {self.interval}s...")
                time.sleep(self.interval)

        self.logger.info(f"Monitor completed {cycle} cycles")
        return cycle
