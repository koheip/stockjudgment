"""Single-process public API protection. Never trust browser-supplied client IDs."""
import copy
import hmac
import os
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone

from fastapi import Header, HTTPException


def production():
    return os.getenv("APP_ENV") == "production" or bool(os.getenv("RENDER"))


def check_configuration():
    if production():
        token = os.getenv("STOCK_API_TOKEN", "")
        if len(token) < 32 or not token.isascii() or not token.isprintable():
            raise RuntimeError("Production requires a printable ASCII STOCK_API_TOKEN of at least 32 characters.")
        if not os.getenv("TYPESAFE_API_KEY", "").strip():
            raise RuntimeError("Production requires TYPESAFE_API_KEY.")


def authorize(x_api_key: str = Header(default="")):
    expected = os.getenv("STOCK_API_TOKEN", "")
    if not expected:
        if production():
            raise HTTPException(503, "公開APIの認証設定が未完了です。")
        return
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "APIの認証に失敗しました。")


class PredictionGuard:
    def __init__(self):
        self.lock = threading.Lock()
        self.work = threading.Lock()
        self.cache = OrderedDict()
        self.requests = deque()
        self.day = ""
        self.calls = 0

    def run(self, key, compute):
        now = time.monotonic()
        with self.lock:
            while self.requests and self.requests[0] <= now - 60:
                self.requests.popleft()
            if len(self.requests) >= int(os.getenv("API_REQUESTS_PER_MINUTE", "30")):
                raise HTTPException(429, "利用が集中しています。1分ほど待って再試行してください。", headers={"Retry-After": "60"})
            self.requests.append(now)
            cached = self.cache.get(key)
            if cached and now < cached[0]:
                self.cache.move_to_end(key)
                return dict(copy.deepcopy(cached[1]), cache_hit=True)
            if cached:
                del self.cache[key]
        # Reject overload instead of allowing an unbounded expensive queue.
        if not self.work.acquire(blocking=False):
            raise HTTPException(503, "別の判定を処理中です。少し待って再試行してください。", headers={"Retry-After": "10"})
        try:
            with self.lock:
                day = datetime.now(timezone.utc).date().isoformat()
                if day != self.day:
                    self.day, self.calls = day, 0
                if self.calls >= int(os.getenv("API_DAILY_COMPUTE_LIMIT", "200")):
                    raise HTTPException(429, "本日の判定上限に達しました。翌日（UTC）に再試行してください。")
                self.calls += 1
            result = compute()
            if result["classification"].get("mode") == "jev":
                with self.lock:
                    self.cache[key] = (time.monotonic() + int(os.getenv("API_CACHE_TTL_SECONDS", "3600")), copy.deepcopy(result))
                    while len(self.cache) > 256:
                        self.cache.popitem(last=False)
            return dict(result, cache_hit=False)
        finally:
            self.work.release()


guard = PredictionGuard()
