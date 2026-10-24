"""Asking the agent to take some work: commit what the backend did for it first,
then ask, and undo it only when the agent definitely didn't start."""

from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy import Connection

from backend.agent_service import Asked, Outcome
from backend.database import engine


def ask[T](
    move: Callable[[Connection], T],
    call: Callable[[T], Asked],
    undo: Callable[[Connection, T], None],
) -> T:
    """Make the move in a transaction of its own, ask the agent, and answer as
    the outcome says."""
    with engine().begin() as connection:
        done = move(connection)
    asked = call(done)
    if asked.outcome is Outcome.NOT_STARTED:
        with engine().begin() as connection:
            undo(connection, done)
        raise HTTPException(asked.status_code, asked.reason)
    if asked.outcome is Outcome.UNKNOWN:
        raise HTTPException(asked.status_code, asked.reason)
    return done
