import re
import xml.etree.ElementTree as ET
from typing import Optional

from apps.api.services.ingestion.models import PackageXmlMetadata


class MalformedXmlError(Exception):
    pass


def parse_package_xml(xml_content: str, rel_path: str = "package.xml") -> PackageXmlMetadata:
    """
    Parses a ROS package.xml file securely supporting format 1, 2, and 3.
    Rejects XML entity injection and malicious structures.
    """
    if not xml_content or not xml_content.strip():
        raise MalformedXmlError("Empty XML content provided.")

    # Defense-in-depth entity declaration check
    if "<!ENTITY" in xml_content.upper() or "<!DOCTYPE" in xml_content.upper():
        raise MalformedXmlError("DOCTYPE and custom ENTITY definitions are forbidden for security.")

    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        raise MalformedXmlError(f"XML parse error: {e}")

    if root.tag != "package":
        raise MalformedXmlError(f"Expected root tag '<package>', found '<{root.tag}>'")

    format_attr = root.attrib.get("format", "1")
    try:
        format_version = int(format_attr)
    except ValueError:
        format_version = 1

    def _get_text(tag: str) -> Optional[str]:
        elem = root.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return None

    def _get_all_text(tag: str) -> list[str]:
        elements = root.findall(tag)
        results = []
        for el in elements:
            if el.text and el.text.strip():
                results.append(el.text.strip())
        return results

    name = _get_text("name")
    if not name:
        raise MalformedXmlError("Missing required '<name>' tag in package.xml.")

    version = _get_text("version") or "0.1.0"
    # Basic semver sanitization
    if not re.match(r"^[0-9]+\.[0-9]+", version):
        version = "0.1.0"
    elif version.count(".") == 1:
        version = f"{version}.0"

    description = _get_text("description")
    license_tag = _get_text("license")

    # Maintainers
    maintainers = []
    for m in root.findall("maintainer"):
        m_text = m.text.strip() if m.text else ""
        email = m.attrib.get("email")
        if email and m_text:
            maintainers.append(f"{m_text} <{email}>")
        elif m_text:
            maintainers.append(m_text)
        elif email:
            maintainers.append(email)

    # Dependencies across formats
    build_depends = _get_all_text("build_depend")
    buildtool_depends = _get_all_text("buildtool_depend")
    test_depends = _get_all_text("test_depend")
    exec_depends = _get_all_text("exec_depend") + _get_all_text("run_depend")
    group_depends = _get_all_text("group_depend")

    # Format 2/3 direct <depend> tags apply to both build and exec
    generic_depends = _get_all_text("depend")
    for dep in generic_depends:
        if dep not in build_depends:
            build_depends.append(dep)
        if dep not in exec_depends:
            exec_depends.append(dep)

    # Export tags
    export_tags = []
    export_elem = root.find("export")
    if export_elem is not None:
        for child in export_elem:
            export_tags.append(child.tag)

    return PackageXmlMetadata(
        name=name,
        version=version,
        description=description,
        maintainers=maintainers,
        license=license_tag,
        build_depends=list(set(build_depends)),
        exec_depends=list(set(exec_depends)),
        test_depends=list(set(test_depends)),
        buildtool_depends=list(set(buildtool_depends)),
        group_depends=list(set(group_depends)),
        export_tags=export_tags,
        format_version=format_version,
        rel_path=rel_path
    )
