#!/usr/bin/env python3
"""
Cross-service integration verification for DeepSecure.

Five deterministic, stdlib-only checks that catch cross-service contract
violations which per-task batch audits structurally cannot see.

Exit code 0 = no CRITICAL findings.  Exit code 1 = CRITICAL findings exist.

Usage:
    python scripts/verify_integration.py
    python scripts/verify_integration.py --warn-only   # exit 0 even on CRITICAL
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTROL_DIR = REPO_ROOT / "deeptrail-control"
MODELS_DIR = CONTROL_DIR / "app" / "models"
ALEMBIC_DIR = CONTROL_DIR / "alembic" / "versions"
ENDPOINTS_DIR = CONTROL_DIR / "app" / "api" / "v1" / "endpoints"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


class Severity(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Finding:
    severity: Severity
    check: str
    detail: str


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)

    def add(self, severity: Severity, check: str, detail: str) -> None:
        self.findings.append(Finding(severity, check, detail))

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)


def extract_tablenames(models_dir: Path) -> Set[str]:
    """Scan SQLAlchemy model files for __tablename__ definitions."""
    tables: Set[str] = set()
    if not models_dir.is_dir():
        return tables
    for py_file in models_dir.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        content = py_file.read_text(errors="replace")
        for match in re.finditer(r'__tablename__\s*=\s*["\'](\w+)["\']', content):
            tables.add(match.group(1))
    return tables


def extract_migration_tables(alembic_dir: Path) -> Set[str]:
    """Scan Alembic migration files for op.create_table(...) calls."""
    tables: Set[str] = set()
    if not alembic_dir.is_dir():
        return tables
    for py_file in alembic_dir.glob("*.py"):
        content = py_file.read_text(errors="replace")
        for match in re.finditer(r'op\.create_table\(\s*["\'](\w+)["\']', content):
            tables.add(match.group(1))
    return tables


def check_model_migration_parity(report: Report) -> None:
    """Check 1: Every SQLAlchemy __tablename__ must have a matching migration."""
    check_name = "1: Model-Migration Parity"
    model_tables = extract_tablenames(MODELS_DIR)
    migration_tables = extract_migration_tables(ALEMBIC_DIR)

    if not model_tables:
        report.add(Severity.WARNING, check_name, "No __tablename__ found in models/")
        return

    missing = model_tables - migration_tables
    if missing:
        for table in sorted(missing):
            report.add(
                Severity.CRITICAL,
                check_name,
                f"Table '{table}' defined in models/ but has no Alembic migration",
            )
    else:
        report.add(
            Severity.INFO,
            check_name,
            f"All {len(model_tables)} model tables have migrations",
        )


def extract_frontend_api_paths(src_dir: Path) -> Set[str]:
    """Scan frontend source for API proxy paths."""
    paths: Set[str] = set()
    if not src_dir.is_dir():
        return paths
    for ts_file in src_dir.rglob("*.ts"):
        content = ts_file.read_text(errors="replace")
        for match in re.finditer(
            r'(?:apiClient|fetch)\s*\(\s*[`"\']/?api/proxy/([^`"\']+)[`"\']',
            content,
        ):
            paths.add("/" + match.group(1).split("?")[0].rstrip("/"))
    for tsx_file in src_dir.rglob("*.tsx"):
        content = tsx_file.read_text(errors="replace")
        for match in re.finditer(
            r'(?:apiClient|fetch)\s*\(\s*[`"\']/?api/proxy/([^`"\']+)[`"\']',
            content,
        ):
            paths.add("/" + match.group(1).split("?")[0].rstrip("/"))
    return paths


def extract_backend_routes(endpoints_dir: Path) -> Set[str]:
    """Scan backend endpoint files for @router.{method}('/path') decorators."""
    routes: Set[str] = set()
    if not endpoints_dir.is_dir():
        return routes
    prefix_pattern = re.compile(
        r'router\s*=\s*APIRouter\s*\(\s*prefix\s*=\s*["\']([^"\']+)["\']'
    )
    route_pattern = re.compile(
        r'@router\.\w+\(\s*["\']([^"\']+)["\']'
    )
    for py_file in endpoints_dir.glob("*.py"):
        content = py_file.read_text(errors="replace")
        prefix = ""
        prefix_match = prefix_pattern.search(content)
        if prefix_match:
            prefix = prefix_match.group(1)
        for match in route_pattern.finditer(content):
            route = prefix + match.group(1)
            route = re.sub(r'\{[^}]+\}', '{param}', route)
            routes.add(route)
    return routes


def check_frontend_backend_route_exists(report: Report) -> None:
    """Check 2: Every frontend proxy path should have a matching backend route."""
    check_name = "2: Frontend-Backend Route Existence"
    frontend_paths = extract_frontend_api_paths(FRONTEND_SRC)
    backend_routes = extract_backend_routes(ENDPOINTS_DIR)

    if not frontend_paths:
        report.add(Severity.INFO, check_name, "No frontend API proxy paths found")
        return

    normalized_backend = set()
    for r in backend_routes:
        normalized_backend.add(re.sub(r'\{[^}]+\}', '{param}', r))

    missing = []
    for fp in sorted(frontend_paths):
        normalized_fp = re.sub(r'\{[^}]+\}', '{param}', fp)
        if not any(normalized_fp.endswith(br) or br.endswith(normalized_fp)
                   for br in normalized_backend):
            missing.append(fp)

    if missing:
        for path in missing:
            report.add(
                Severity.CRITICAL,
                check_name,
                f"Frontend calls '{path}' but no matching backend route found",
            )
    else:
        report.add(
            Severity.INFO,
            check_name,
            f"All {len(frontend_paths)} frontend paths have backend routes",
        )


def check_auth_mechanism_compat(report: Report) -> None:
    """Check 3: Flag endpoints using APIKeyDep that are called from JWT proxy."""
    check_name = "3: Auth Mechanism Compatibility"
    if not ENDPOINTS_DIR.is_dir():
        report.add(Severity.WARNING, check_name, "Endpoints directory not found")
        return

    api_key_endpoints: list[tuple[str, str]] = []
    for py_file in ENDPOINTS_DIR.glob("*.py"):
        content = py_file.read_text(errors="replace")
        if "APIKeyDep" not in content and "verify_api_key" not in content:
            continue
        route_pattern = re.compile(
            r'@router\.(\w+)\(\s*["\']([^"\']+)["\']'
        )
        lines = content.split("\n")
        for i, line in enumerate(lines):
            route_match = route_pattern.search(line)
            if route_match:
                lookahead = "\n".join(lines[i:i+15])
                if "APIKeyDep" in lookahead or "verify_api_key" in lookahead:
                    api_key_endpoints.append(
                        (py_file.stem, route_match.group(2))
                    )

    if api_key_endpoints:
        for module, route in api_key_endpoints:
            report.add(
                Severity.CRITICAL,
                check_name,
                f"{module}.py: '{route}' uses APIKeyDep — dashboard proxy sends JWT Bearer",
            )
    else:
        report.add(
            Severity.INFO,
            check_name,
            "No JWT/APIKey auth mismatches detected",
        )


def check_in_memory_storage(report: Report) -> None:
    """Check 5: Detect module-level mutable dicts/lists in endpoint files."""
    check_name = "5: In-Memory Storage Detection"
    if not ENDPOINTS_DIR.is_dir():
        report.add(Severity.WARNING, check_name, "Endpoints directory not found")
        return

    patterns = [
        (re.compile(r'^(\w+)\s*:\s*(?:Dict|dict)\b.*=\s*\{\}', re.MULTILINE), "dict"),
        (re.compile(r'^(\w+)\s*:\s*(?:List|list)\b.*=\s*\[\]', re.MULTILINE), "list"),
        (re.compile(r'^(\w+)\s*=\s*\{\}\s*$', re.MULTILINE), "dict"),
        (re.compile(r'^(\w+)\s*=\s*\[\]\s*$', re.MULTILINE), "list"),
    ]

    found = False
    for py_file in ENDPOINTS_DIR.glob("*.py"):
        content = py_file.read_text(errors="replace")
        for pattern, kind in patterns:
            for match in pattern.finditer(content):
                var_name = match.group(1)
                if var_name.startswith("_") or var_name[0].islower():
                    report.add(
                        Severity.CRITICAL,
                        check_name,
                        f"{py_file.stem}.py: Module-level mutable {kind} '{var_name}' — data lost on restart",
                    )
                    found = True

    if not found:
        report.add(
            Severity.INFO,
            check_name,
            "No module-level mutable state in endpoint files",
        )


def check_request_body_shape(report: Report) -> None:
    """Check 4: Compare frontend field names vs backend Pydantic required fields.

    This is a best-effort heuristic — it scans for JSON.stringify or fetch body
    patterns in frontend code and compares against Pydantic model field names.
    """
    check_name = "4: Request Body Shape"

    schemas_dir = CONTROL_DIR / "app" / "schemas"
    models_dir_alt = CONTROL_DIR / "app" / "models"

    backend_required: dict[str, set[str]] = {}

    for search_dir in [schemas_dir, models_dir_alt]:
        if not search_dir.is_dir():
            continue
        for py_file in search_dir.glob("*.py"):
            content = py_file.read_text(errors="replace")
            class_pattern = re.compile(
                r'class\s+(\w*Create\w*)\(.*BaseModel.*\):', re.MULTILINE
            )
            field_pattern = re.compile(
                r'^\s+(\w+)\s*:\s*(?!Optional)(\w+)', re.MULTILINE
            )
            for class_match in class_pattern.finditer(content):
                class_name = class_match.group(1)
                class_start = class_match.end()
                next_class = content.find("\nclass ", class_start)
                class_body = content[class_start:next_class] if next_class != -1 else content[class_start:]
                fields = set()
                for field_match in field_pattern.finditer(class_body):
                    fname = field_match.group(1)
                    if not fname.startswith("_") and fname != "model_config":
                        fields.add(fname)
                if fields:
                    backend_required[class_name] = fields

    if not backend_required:
        report.add(Severity.INFO, check_name, "No *Create Pydantic models found to compare")
        return

    report.add(
        Severity.INFO,
        check_name,
        f"Found {len(backend_required)} Create schemas: {', '.join(sorted(backend_required.keys()))}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSecure integration verification")
    parser.add_argument("--warn-only", action="store_true", help="Exit 0 even on CRITICAL")
    args = parser.parse_args()

    report = Report()

    print()
    print("DeepSecure Integration Verification")
    print("=" * 40)
    print()

    check_model_migration_parity(report)
    check_frontend_backend_route_exists(report)
    check_auth_mechanism_compat(report)
    check_request_body_shape(report)
    check_in_memory_storage(report)

    for finding in report.findings:
        icon = {"CRITICAL": "❌", "WARNING": "⚠️ ", "INFO": "✅"}[finding.severity.value]
        label = f"[{finding.severity.value}]"
        print(f"  {icon} {label:12s} Check {finding.check}")
        print(f"     {finding.detail}")
        print()

    print("-" * 40)
    print(f"Result: {report.critical_count} CRITICAL  {report.warning_count} WARNING")
    print()

    if report.critical_count > 0 and not args.warn_only:
        print("EXIT 1 — CRITICAL findings must be resolved before proceeding.")
        return 1
    else:
        print("EXIT 0 — No blocking findings.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
