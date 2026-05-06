from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests
from requests import Response
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class RetryableHttpError(RuntimeError):
    pass


class HttpStatusError(RuntimeError):
    def __init__(self, status_code: int, url: str, message: str | None = None):
        self.status_code = status_code
        self.url = url
        super().__init__(message or f"HTTP status {status_code} for url: {url}")


def build_user_agent(contact_email: str | None = None) -> str:
    suffix = f" ({contact_email})" if contact_email else ""
    return f"paper-radar/0.1 compliant-metadata-crawler{suffix}"


@retry(
    retry=retry_if_exception_type((requests.RequestException, RetryableHttpError)),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    response = session.request(method, url, params=params, headers=headers, timeout=timeout)
    _raise_for_status(response)
    return response.json()


@retry(
    retry=retry_if_exception_type((requests.RequestException, RetryableHttpError)),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def request_text(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> str:
    response = session.request(method, url, params=params, headers=headers, timeout=timeout)
    _raise_for_status(response)
    return response.text


def _raise_for_status(response: Response) -> None:
    if response.status_code == 429 or 500 <= response.status_code <= 599:
        raise RetryableHttpError(f"retryable HTTP status {response.status_code}")
    if response.status_code >= 400:
        raise HttpStatusError(response.status_code, response.url)
