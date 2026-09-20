"""Domain-level exceptions raised by services/complaints.py.

Both carry exactly the data a future route layer (Phase 7) needs to build
its HTTP-level response — neither exception knows about HTTP status codes
or response shapes, per CLAUDE.md's four-layer rule.
"""

import uuid


class IllegalTransitionError(Exception):
    def __init__(self, current_status: str, attempted_status: str) -> None:
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(f"{current_status} -> {attempted_status} is not a legal transition")


class NotFoundError(Exception):
    def __init__(self, complaint_id: uuid.UUID) -> None:
        self.complaint_id = complaint_id
        super().__init__(f"complaint {complaint_id} not found")
