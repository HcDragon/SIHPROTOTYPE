from enum import StrEnum


class Role(StrEnum):
    """The fixed FlowGuard roles. One per user; never created or renamed at runtime."""

    SUPER_ADMIN = "super_admin"
    AICTE_ADMIN = "aicte_admin"
    REGIONAL_OFFICER = "regional_officer"
    SCRUTINY_OFFICER = "scrutiny_officer"
    EVC_COORDINATOR = "evc_coordinator"
    INSTITUTION_REPRESENTATIVE = "institution_representative"
    AUDITOR = "auditor"


ROLE_LABELS: dict[Role, str] = {
    Role.SUPER_ADMIN: "Super Admin",
    Role.AICTE_ADMIN: "AICTE Admin",
    Role.REGIONAL_OFFICER: "Regional Officer",
    Role.SCRUTINY_OFFICER: "Scrutiny Officer",
    Role.EVC_COORDINATOR: "EVC Coordinator",
    Role.INSTITUTION_REPRESENTATIVE: "Institution Representative",
    Role.AUDITOR: "Auditor",
}
