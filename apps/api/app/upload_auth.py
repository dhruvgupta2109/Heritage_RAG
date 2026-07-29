import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

import bcrypt


class InvalidUploadPassword(Exception):
    pass


class UploadRateLimited(Exception):
    pass


class UploadAccess:
    def __init__(
        self,
        password_hash: str,
        session_ttl_seconds: int = 600,
        max_attempts: int = 5,
        attempt_window_seconds: int = 600,
    ):
        self.password_hash = password_hash.encode("utf-8")
        self.session_ttl_seconds = session_ttl_seconds
        self.max_attempts = max_attempts
        self.attempt_window_seconds = attempt_window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    def unlock(self, password: str, client_key: str, now: float | None = None) -> str:
        current_time = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._active_attempts(client_key, current_time)
            if len(attempts) >= self.max_attempts:
                raise UploadRateLimited

        try:
            valid = bcrypt.checkpw(password.encode("utf-8"), self.password_hash)
        except (ValueError, TypeError):
            valid = False

        if not valid:
            with self._lock:
                attempts = self._active_attempts(client_key, current_time)
                attempts.append(current_time)
            raise InvalidUploadPassword

        token = secrets.token_urlsafe(32)
        token_digest = self._token_digest(token)
        with self._lock:
            self._attempts.pop(client_key, None)
            self._remove_expired_sessions(current_time)
            self._sessions[token_digest] = current_time + self.session_ttl_seconds
        return token

    def is_unlocked(self, token: str | None, now: float | None = None) -> bool:
        if not token:
            return False
        current_time = time.monotonic() if now is None else now
        token_digest = self._token_digest(token)
        with self._lock:
            self._remove_expired_sessions(current_time)
            expires_at = self._sessions.get(token_digest)
        return expires_at is not None and expires_at > current_time

    def _active_attempts(self, client_key: str, now: float) -> deque[float]:
        attempts = self._attempts[client_key]
        cutoff = now - self.attempt_window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return attempts

    def _remove_expired_sessions(self, now: float) -> None:
        expired = [token for token, expires_at in self._sessions.items() if expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
