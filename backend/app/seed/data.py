"""Fictional demo accounts. Names are invented; emails use the reserved example.org domain."""

from dataclasses import dataclass

from app.access.roles import Role

DEMO_DOMAIN = "flowguard.example.org"


@dataclass(frozen=True)
class DemoUser:
    email: str
    full_name: str
    role: Role
    is_active: bool = True


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(f"super.admin@{DEMO_DOMAIN}", "Demo Super Admin (Kavya Iyer)", Role.SUPER_ADMIN),
    DemoUser(f"aicte.admin@{DEMO_DOMAIN}", "Demo AICTE Admin (Rohan Mehta)", Role.AICTE_ADMIN),
    DemoUser(
        f"regional.officer@{DEMO_DOMAIN}",
        "Demo Regional Officer (Ananya Das)",
        Role.REGIONAL_OFFICER,
    ),
    DemoUser(
        f"scrutiny.officer@{DEMO_DOMAIN}",
        "Demo Scrutiny Officer (Vikram Nair)",
        Role.SCRUTINY_OFFICER,
    ),
    DemoUser(
        f"evc.coordinator@{DEMO_DOMAIN}",
        "Demo EVC Coordinator (Farah Khan)",
        Role.EVC_COORDINATOR,
    ),
    DemoUser(
        f"institution.rep@{DEMO_DOMAIN}",
        "Demo Institution Representative (Arjun Patel)",
        Role.INSTITUTION_REPRESENTATIVE,
    ),
    DemoUser(f"auditor@{DEMO_DOMAIN}", "Demo Auditor (Neha Joshi)", Role.AUDITOR),
    DemoUser(
        f"inactive.officer@{DEMO_DOMAIN}",
        "Demo Deactivated Officer (Sameer Gupta)",
        Role.SCRUTINY_OFFICER,
        is_active=False,
    ),
)
