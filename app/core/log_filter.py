import logging

from app.core.request_context import (
    get_request_id,
)


class RequestIdFilter(logging.Filter):

    def filter(self, record):
        try:
            record.request_id = get_request_id()
        except Exception:
            record.request_id = "-"

        return True