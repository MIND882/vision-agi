# roles/role_factory.py
# ============================================================
# ROLE FACTORY — Create any Digital Human in one line.
#
# Usage:
#   from roles.role_factory import RoleFactory
#
#   aria  = RoleFactory.create("aria")
#   max   = RoleFactory.create("sales")
#   priya = RoleFactory.create("hr")
#   rohan = RoleFactory.create("support")
#
#   # All have same interface:
#   response = aria.chat("Mera AC kharab hai")
#   response = max.chat("I need pricing info")
#   response = priya.chat("Leave apply karna hai")
#   response = rohan.chat("Order nahi aaya")
# ============================================================

from role.base_role import BaseRole
from role.ac_service import ACSServiceRole
from role.sales_agent import SalesAgentRole
from role.hr_assistant import HRAssistantRole
from role.support_agent import SupportAgentRole


# ── Role Registry ─────────────────────────────────────────────
# Add new roles here — factory auto-discovers them
ROLE_REGISTRY: dict[str, type[BaseRole]] = {
    # AC Service
    "aria":         ACSServiceRole,
    "ac":           ACSServiceRole,
    "ac_service":   ACSServiceRole,

    # Sales Agent
    "max":          SalesAgentRole,
    "sales":        SalesAgentRole,
    "sales_agent":  SalesAgentRole,

    # HR Assistant
    "priya":        HRAssistantRole,
    "hr":           HRAssistantRole,
    "hr_assistant": HRAssistantRole,

    # Support Agent
    "rohan":        SupportAgentRole,
    "support":      SupportAgentRole,
    "support_agent": SupportAgentRole,
}


class RoleFactory:
    """Factory to create any Digital Human role."""

    @staticmethod
    def create(role_name: str) -> BaseRole:
        """
        Create a Digital Human by role name.

        Args:
            role_name: "aria" | "max" | "priya" | "rohan"
                       or aliases: "ac" | "sales" | "hr" | "support"

        Returns:
            Fully initialized Digital Human ready to chat.

        Raises:
            ValueError: if role_name not found in registry.
        """
        key = role_name.lower().strip()

        role_class = ROLE_REGISTRY.get(key)
        if not role_class:
            available = sorted(set(ROLE_REGISTRY.keys()))
            raise ValueError(
                f"Role '{role_name}' not found.\n"
                f"Available roles: {available}"
            )

        return role_class()

    @staticmethod
    def available_roles() -> list[str]:
        """Return list of unique role names (no aliases)."""
        return ["aria", "max", "priya", "rohan"]

    @staticmethod
    def list_all() -> dict:
        """Return all roles with their details."""
        roles = {}
        for name in RoleFactory.available_roles():
            try:
                instance = RoleFactory.create(name)
                cfg      = instance.config
                roles[name] = {
                    "name":    cfg.name,
                    "role":    cfg.role,
                    "company": cfg.company,
                    "industry": cfg.industry,
                    "tools":   cfg.tools_enabled,
                }
            except Exception as e:
                roles[name] = {"error": str(e)}
        return roles


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Available roles:")
    for name, details in RoleFactory.list_all().items():
        print(f"\n  {details['name']} ({name})")
        print(f"    Role    : {details['role']}")
        print(f"    Company : {details['company']}")
        print(f"    Industry: {details['industry']}")
        print(f"    Tools   : {details['tools']}")