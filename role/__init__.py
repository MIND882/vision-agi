# roles/__init__.py
from role.role_factory import RoleFactory
from role.base_role import BaseRole, RoleConfig

__all__ = ["RoleFactory", "BaseRole", "RoleConfig"]