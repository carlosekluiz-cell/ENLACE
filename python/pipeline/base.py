"""Base pipeline class for all data ingestion flows."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
import psycopg2
from python.pipeline.config import DatabaseConfig

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """Abstract base class for data ingestion pipelines.

    Lifecycle: check_for_updates() -> download() -> validate_raw() -> transform() -> load() -> post_load()
    All steps are logged to pipeline_runs table.
    """

    def __init__(self, name: str, db_config: Optional[DatabaseConfig] = None):
        self.name = name
        self.db_config = db_config or DatabaseConfig()
        self.run_id: Optional[int] = None
        self.rows_processed = 0
        self.rows_inserted = 0
        self.rows_updated = 0

    def run(self, force: bool = False) -> dict:
        """Execute the full pipeline. Returns summary dict."""
        self._start_run()
        try:
            if not force and not self.check_for_updates():
                logger.info(f"[{self.name}] No updates available")
                self._complete_run("skipped")
                return {"status": "skipped", "reason": "no_updates"}

            logger.info(f"[{self.name}] Downloading...")
            raw_data = self.download()

            logger.info(f"[{self.name}] Validating raw data...")
            self.validate_raw(raw_data)

            logger.info(f"[{self.name}] Transforming...")
            transformed = self.transform(raw_data)

            logger.info(f"[{self.name}] Loading...")
            self.load(transformed)

            logger.info(f"[{self.name}] Post-load tasks...")
            self.post_load()

            self._complete_run("success")
            return {
                "status": "success",
                "rows_processed": self.rows_processed,
                "rows_inserted": self.rows_inserted,
                "rows_updated": self.rows_updated,
            }
        except Exception as e:
            logger.error(f"[{self.name}] Failed: {e}")
            self._complete_run("failed", str(e))
            raise

    @abstractmethod
    def check_for_updates(self) -> bool:
        """Check if new data is available. Return True if pipeline should run."""
        ...

    @abstractmethod
    def download(self) -> Any:
        """Download raw data from source. Returns raw data (DataFrame, bytes, etc.)."""
        ...

    def validate_raw(self, data: Any) -> None:
        """Validate raw data schema and bounds. Override for custom validation."""
        pass

    @abstractmethod
    def transform(self, raw_data: Any) -> Any:
        """Transform raw data into load-ready format."""
        ...

    @abstractmethod
    def load(self, data: Any) -> None:
        """Load transformed data into PostgreSQL."""
        ...

    def post_load(self) -> None:
        """Post-load tasks (refresh views, update caches). Override as needed."""
        pass

    def _get_connection(self):
        return psycopg2.connect(self.db_config.url)

    def _start_run(self):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO pipeline_runs (pipeline_name, started_at, status) VALUES (%s, %s, 'running') RETURNING id",
            (self.name, datetime.utcnow())
        )
        self.run_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

    def _complete_run(self, status: str, error_msg: str = None):
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            """UPDATE pipeline_runs SET completed_at=%s, status=%s,
               rows_processed=%s, rows_inserted=%s, rows_updated=%s, error_message=%s
               WHERE id=%s""",
            (datetime.utcnow(), status, self.rows_processed, self.rows_inserted,
             self.rows_updated, error_msg, self.run_id)
        )
        conn.commit()
        cur.close()
        conn.close()
