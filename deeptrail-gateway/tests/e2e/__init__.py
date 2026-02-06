"""
End-to-End Tests for Virtual MCP Server MVP.

This package contains E2E tests that validate the complete system:
- Sarah's Journey (F1): All 10 steps from design document
- Demo scripts (F2-F6): Individual demo validations

These tests require both Control Plane and Gateway running.

Usage:
    # Start services
    docker compose up -d db redis deeptrail-control deeptrail-gateway

    # Run E2E tests
    pytest tests/e2e/ -v -m e2e

    # Run specific journey
    pytest tests/e2e/test_sarah_journey.py -v
"""
