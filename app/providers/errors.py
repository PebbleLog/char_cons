"""Provider 统一错误。错误码与技术方案 14.2 对齐。"""

from __future__ import annotations


class ProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after = retry_after


def is_fatal(code: str) -> bool:
    """鉴权/额度/内容安全不重试，也通常不应继续后续调用。"""
    return code in {"auth_failed", "quota_exceeded", "content_filtered"}
