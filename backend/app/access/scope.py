"""Record-scope hook. Later modules (institutions, applications) filter queries by Scope.

A record outside the caller's scope is reported exactly like a record that does not exist.
"""

import uuid
from dataclasses import dataclass

from app.access.roles import Role
from app.core.errors import NotFound


@dataclass(frozen=True)
class Scope:
    user_id: uuid.UUID
    role: Role
    # Filled in when institutions and regions exist; None means "not restricted by this field".
    institution_id: uuid.UUID | None = None
    region_id: uuid.UUID | None = None

    @classmethod
    def for_user(cls, user) -> "Scope":
        return cls(user_id=user.id, role=Role(user.role))


def found_in_scope[T](record: T | None) -> T:
    """Return the record from a scope-filtered lookup, or raise the standard 404."""
    if record is None:
        raise NotFound()
    return record
