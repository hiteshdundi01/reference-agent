"""Signing in: password hashes, and the short-lived tokens users carry. The one
module that knows how a user is identified, so a move to an identity provider
changes only this module."""

import os
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
LIFETIME = timedelta(hours=8)
NOT_SET_UP = "AUTH_SECRET is missing. Add it to .env"

hasher = PasswordHash.recommended()


class BadToken(Exception):
    """A token that is missing, malformed, expired or not ours."""


def secret() -> str:
    """The secret that signs tokens, read as each token is made or checked."""
    value = os.getenv("AUTH_SECRET")
    if not value:
        raise RuntimeError(NOT_SET_UP)
    return value


def hash_password(password: str) -> str:
    return hasher.hash(password)


def password_matches(password: str, password_hash: str) -> bool:
    return hasher.verify(password, password_hash)


def token_for(email: str) -> str:
    """A token naming the user, good for LIFETIME."""
    expires = datetime.now(UTC) + LIFETIME
    return jwt.encode({"sub": email, "exp": expires}, secret(), algorithm=ALGORITHM)


def email_in(token: str) -> str:
    """The email a token names, or BadToken."""
    try:
        claims = jwt.decode(
            token, secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
    except jwt.InvalidTokenError as error:
        raise BadToken(str(error)) from error
    return claims["sub"]
