#!/usr/bin/env python3
"""One-off script to normalize Exa MCP permission strings.

Migrates from the old {service_id}:tools:{tool_name} format to the
canonical {service}:{resource}:{action} format:

    exa:tools:web_search_exa  ->  exa:web:search
    exa:tools:web_fetch_exa   ->  exa:web:fetch

Updates:
  1. service_registry.permission_map  (Exa's row)
  2. delegation_templates.max_permissions  (any containing exa:tools:*)
  3. delegation_tokens.delegated_permissions  (any containing exa:tools:*)

This is a JSONB data update, NOT a schema migration.  No Alembic needed.

Usage:
    # Dry run (default):
    python scripts/normalize_exa_permissions.py

    # Apply changes:
    python scripts/normalize_exa_permissions.py --apply

Requires DATABASE_URL or the standard deeptrail-control environment.
"""

import argparse
import json
import os
import sys

OLD_TO_NEW = {
    "exa:tools:web_search_exa": "exa:web:search",
    "exa:tools:web_fetch_exa": "exa:web:fetch",
}


def get_connection():
    """Get a psycopg2 connection from DATABASE_URL or fallback defaults."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed.  pip install psycopg2-binary")
        sys.exit(1)

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://deepsecure_user:deepsecure_pass@localhost:5434/deeptrail_controldb",
    )
    return psycopg2.connect(db_url)


def normalize_permission_map(pmap: dict) -> tuple[dict, bool]:
    """Return (updated_map, changed) for a service_registry permission_map."""
    updated = dict(pmap)
    changed = False
    for tool_name, perm in list(updated.items()):
        if perm in OLD_TO_NEW:
            updated[tool_name] = OLD_TO_NEW[perm]
            changed = True
    return updated, changed


def normalize_permission_list(perms: list) -> tuple[list, bool]:
    """Return (updated_list, changed) for a permissions list/array."""
    updated = []
    changed = False
    for p in perms:
        if p in OLD_TO_NEW:
            updated.append(OLD_TO_NEW[p])
            changed = True
        else:
            updated.append(p)
    return updated, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry run)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Mapping: {json.dumps(OLD_TO_NEW, indent=2)}\n")

    # 1. service_registry
    cur.execute("SELECT service_id, permission_map FROM service_registry WHERE permission_map IS NOT NULL")
    for service_id, pmap in cur.fetchall():
        if not pmap:
            continue
        updated, changed = normalize_permission_map(pmap)
        if changed:
            print(f"[service_registry] {service_id}: {pmap} -> {updated}")
            if args.apply:
                cur.execute(
                    "UPDATE service_registry SET permission_map = %s WHERE service_id = %s",
                    (json.dumps(updated), service_id),
                )

    # 2. delegation_templates
    cur.execute("SELECT id, name, max_permissions FROM delegation_templates WHERE max_permissions IS NOT NULL")
    for tid, name, perms in cur.fetchall():
        if not perms:
            continue
        updated, changed = normalize_permission_list(perms)
        if changed:
            print(f"[delegation_templates] {name} (id={tid}): updated {sum(1 for o, n in zip(perms, updated) if o != n)} permissions")
            if args.apply:
                cur.execute(
                    "UPDATE delegation_templates SET max_permissions = %s WHERE id = %s",
                    (json.dumps(updated), tid),
                )

    # 3. delegation_tokens
    cur.execute("SELECT id, delegated_permissions FROM delegation_tokens WHERE delegated_permissions IS NOT NULL")
    for did, perms in cur.fetchall():
        if not perms:
            continue
        updated, changed = normalize_permission_list(perms)
        if changed:
            print(f"[delegation_tokens] id={did}: updated {sum(1 for o, n in zip(perms, updated) if o != n)} permissions")
            if args.apply:
                cur.execute(
                    "UPDATE delegation_tokens SET delegated_permissions = %s WHERE id = %s",
                    (json.dumps(updated), did),
                )

    if args.apply:
        conn.commit()
        print("\nChanges committed.")
    else:
        conn.rollback()
        print("\nDry run complete. Use --apply to commit changes.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
