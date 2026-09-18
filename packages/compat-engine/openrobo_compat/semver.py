from typing import Optional, Tuple

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def clean_version_str(version_str: str) -> str:
    """Cleans version strings by stripping prefixes like 'v' and trailing metadata."""
    if not version_str:
        return ""
    v = version_str.strip().lstrip("vV")
    v = v.split("+")[0]
    return v


def parse_semver_constraint(constraint_str: str) -> SpecifierSet:
    """
    Parses and translates various semantic version formats into a standard packaging SpecifierSet.
    Supports:
      - Caret ranges: ^1.2.3 (>=1.2.3, <2.0.0), ^0.2.3 (>=0.2.3, <0.3.0)
      - Tilde ranges: ~1.2.3 (~=1.2.3)
      - Wildcards: 1.x, 1.* (>=1.0.0, <2.0.0)
      - Standard PEP 440 / SemVer combinations: >=2.1.0,<3.0.0, ==1.5.2
    """
    if not constraint_str or constraint_str.strip() in ("*", "any", "latest"):
        return SpecifierSet()

    raw = constraint_str.strip()

    # Caret range: ^1.2.3 or ^0.2.3
    if raw.startswith("^"):
        v_part = clean_version_str(raw[1:])
        try:
            parsed = Version(v_part)
            major, minor = parsed.major, parsed.minor
            if major > 0:
                next_major = major + 1
                return SpecifierSet(f">={v_part},<{next_major}.0.0")
            elif minor > 0:
                next_minor = minor + 1
                return SpecifierSet(f">={v_part},<0.{next_minor}.0")
            else:
                return SpecifierSet(f"=={v_part}")
        except InvalidVersion:
            pass

    # Tilde range: ~1.2.3 -> ~=1.2.3
    if raw.startswith("~") and not raw.startswith("~="):
        v_part = clean_version_str(raw[1:])
        return SpecifierSet(f"~={v_part}")

    # Wildcard: 1.x or 1.* -> >=1.0.0, <2.0.0
    import re

    wildcard_match = re.match(r"^(\d+)\.(x|\*)$", raw, re.IGNORECASE)
    if wildcard_match:
        major = int(wildcard_match.group(1))
        return SpecifierSet(f">={major}.0.0,<{major + 1}.0.0")

    wildcard_minor = re.match(r"^(\d+)\.(\d+)\.(x|\*)$", raw, re.IGNORECASE)
    if wildcard_minor:
        major = int(wildcard_minor.group(1))
        minor = int(wildcard_minor.group(2))
        return SpecifierSet(f">={major}.{minor}.0,<{major}.{minor + 1}.0")

    try:
        return SpecifierSet(raw)
    except InvalidSpecifier:
        clean = clean_version_str(raw)
        try:
            return SpecifierSet(f"=={clean}")
        except InvalidSpecifier:
            return SpecifierSet()


def matches_version_constraint(version_str: Optional[str], constraint_str: Optional[str]) -> Tuple[bool, str]:
    """
    Evaluates if a given version string satisfies a semantic version constraint.
    Returns (matches: bool, explanation: str).
    """
    if not constraint_str or constraint_str.strip() in ("", "*", "any"):
        return True, "No constraint specified"

    if not version_str:
        return False, f"Version is missing; cannot satisfy constraint '{constraint_str}'"

    clean_v = clean_version_str(version_str)
    try:
        parsed_v = Version(clean_v)
    except InvalidVersion:
        return False, f"Invalid version string '{version_str}'"

    spec_set = parse_semver_constraint(constraint_str)
    if not spec_set:
        if clean_v == clean_version_str(constraint_str):
            return True, f"Exact version match for '{clean_v}'"
        return True, f"Constraint '{constraint_str}' evaluated as open"

    if parsed_v in spec_set:
        return True, f"Version '{clean_v}' satisfies constraint '{constraint_str}'"
    else:
        return (
            False,
            f"Version '{clean_v}' violates constraint '{constraint_str}'",
        )
