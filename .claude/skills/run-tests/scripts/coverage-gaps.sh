#!/bin/bash
# coverage-gaps.sh — Find Python source files that have no corresponding test file
# Used by the run-tests skill to identify missing test coverage

echo "=== Source files without test files ==="
find deepsecure -name "*.py" -not -name "__init__.py" -not -path "*/migrations/*" | while read src; do
    base=$(basename "$src" .py)
    # Look for any test file matching this module
    test_file=$(find tests -name "test_${base}.py" -o -name "test_*${base}*.py" 2>/dev/null | head -1)
    if [ -z "$test_file" ]; then
        echo "  MISSING: $src → no test_${base}.py found"
    fi
done

echo ""
echo "=== Test pyramid distribution ==="
unit=$(find tests -name "test_*.py" -not -path "*/e2e/*" -not -path "*/integration/*" | wc -l | tr -d ' ')
e2e=$(find tests -name "test_*.py" -path "*/e2e/*" 2>/dev/null | wc -l | tr -d ' ')
integration=$(grep -rl "pytest.mark.integration" tests/ 2>/dev/null | wc -l | tr -d ' ')
total=$((unit + e2e + integration))
if [ "$total" -gt 0 ]; then
    echo "  Unit:        $unit ($(( unit * 100 / total ))%)"
    echo "  Integration: $integration ($(( integration * 100 / total ))%)"
    echo "  E2E:         $e2e ($(( e2e * 100 / total ))%)"
    echo "  Target:      80% unit / 15% integration / 5% e2e"
else
    echo "  No test files found"
fi
