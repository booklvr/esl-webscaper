from __future__ import annotations

import random
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = "esl-webscraper/0.1 (+https://example.local/contact)"


@dataclass(slots=True)
class FetchPolicy:
    min_delay_seconds: float = 1.0
    max_delay_seconds: float = 2.5
    timeout_seconds: float = 20.0


class SimpleResponse:
    def __init__(self, text: str, status_code: int, url: str) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url


class PoliteHttpClient:
    def __init__(self, policy: FetchPolicy | None = None) -> None:
        self.policy = policy or FetchPolicy()
        self._robots_cache: dict[str, RobotFileParser] = {}

    def _robots_parser(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots_cache:
            return self._robots_cache[origin]

        robots = RobotFileParser()
        robots.set_url(urljoin(origin, "/robots.txt"))
        try:
            robots.read()
        except Exception:
            pass
        self._robots_cache[origin] = robots
        return robots

    def get(self, url: str) -> SimpleResponse:
        robots = self._robots_parser(url)
        if not robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"Blocked by robots.txt: {url}")

        sleep_for = random.uniform(self.policy.min_delay_seconds, self.policy.max_delay_seconds)
        time.sleep(sleep_for)

        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=self.policy.timeout_seconds) as response:  # noqa: S310
            status_code = response.getcode()
            body = response.read().decode("utf-8", errors="replace")
            final_url = response.geturl()

        if status_code >= 400:
            raise RuntimeError(f"HTTP error {status_code} for {url}")
        return SimpleResponse(text=body, status_code=status_code, url=final_url)

    def close(self) -> None:
        return None
