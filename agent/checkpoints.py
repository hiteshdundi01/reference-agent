"""Where the agent's graph keeps its progress: SqliteSaver on the file
CHECKPOINT_DB names, one saver for the process."""

import os
import sqlite3
from functools import cache

from langgraph.checkpoint.sqlite import SqliteSaver

CHECKPOINT_DB = "CHECKPOINT_DB"
DEFAULT_DB = "checkpoints.db"


@cache
def saver_at(path: str) -> SqliteSaver:
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


def saver() -> SqliteSaver:
    """The process's saver on CHECKPOINT_DB, read on each call so that a test can
    point it at a file of its own."""
    return saver_at(os.getenv(CHECKPOINT_DB, DEFAULT_DB))
