"""Who may call what: the gates every route but the health check and sign-in has.

The agent's key never stands in for a person, and a person's token never opens
the agent's routes."""

import os
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from backend import auth
from backend.database import engine, users
from backend.models import User

API_KEY_HEADER = "X-API-Key"
AGENT_KEY = "AGENT_KEY"
SIGN_IN_AGAIN = "Your sign-in has expired or isn't valid; sign in again"

agent_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)
bearer = HTTPBearer(auto_error=False)
KeyGiven = Annotated[str | None, Depends(agent_key_header)]
TokenGiven = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def check_agent_key(
    key: str | None, token: HTTPAuthorizationCredentials | None
) -> None:
    if token is not None:
        raise HTTPException(
            403, "A person's sign-in can't be used on the agent's routes"
        )
    expected = os.getenv(AGENT_KEY)
    if not expected:
        raise HTTPException(
            401, "No agent key is set up, so the agent's routes are closed"
        )
    if key is None or not compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "The agent's key is missing or wrong")


def check_sign_in(key: str | None, token: HTTPAuthorizationCredentials | None) -> User:
    if key is not None:
        raise HTTPException(403, "The agent's key can't be used on a person's routes")
    if token is None:
        raise HTTPException(401, "Sign in first")
    try:
        email = auth.email_in(token.credentials)
    except auth.BadToken as error:
        raise HTTPException(401, SIGN_IN_AGAIN) from error
    with engine().connect() as connection:
        row = connection.execute(select(users).where(users.c.email == email)).first()
    if row is None:
        raise HTTPException(401, SIGN_IN_AGAIN)
    return User(email=row.email, name=row.name, role=row.role)


def agent(key: KeyGiven, token: TokenGiven) -> None:
    """The agent, with its key."""
    check_agent_key(key, token)


def signed_in(key: KeyGiven, token: TokenGiven) -> User:
    """A signed-in rep or supervisor."""
    return check_sign_in(key, token)


def supervisor(user: Annotated[User, Depends(signed_in)]) -> User:
    """A signed-in supervisor."""
    if user.role != "supervisor":
        raise HTTPException(403, "Only a supervisor can sign off or send back a refund")
    return user


def agent_or_person(key: KeyGiven, token: TokenGiven) -> None:
    """The agent with its key, or a signed-in person, for the reads both make."""
    if key is not None:
        check_agent_key(key, token)
    else:
        check_sign_in(key, token)


AgentKey = Depends(agent)
AgentOrPerson = Depends(agent_or_person)
SignedIn = Annotated[User, Depends(signed_in)]
Supervisor = Annotated[User, Depends(supervisor)]
