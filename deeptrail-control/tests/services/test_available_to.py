"""Tests for AvailableToEvaluator (CR-2)."""

import pytest

from app.services.available_to import AvailableToEvaluator
from app.services.role_resolver import UserContext


@pytest.fixture()
def evaluator():
    return AvailableToEvaluator()


def _user(sub: str = "user@test.com", roles=None, groups=None) -> UserContext:
    return UserContext(
        sub=sub,
        roles=roles or ["employee"],
        groups=groups or [],
    )


class TestAvailableToMatrix:
    def test_all_grants_everyone(self, evaluator):
        assert evaluator.is_visible(["all"], [], [], _user(roles=["engineer"]))

    def test_empty_lists_visible_to_nobody(self, evaluator):
        assert not evaluator.is_visible([], [], [], _user(roles=["admin"]))

    def test_role_match(self, evaluator):
        assert evaluator.is_visible(["sales"], [], [], _user(roles=["sales"]))
        assert not evaluator.is_visible(["sales"], [], [], _user(roles=["engineer"]))

    def test_group_match(self, evaluator):
        assert evaluator.is_visible([], ["designers"], [], _user(groups=["designers"]))

    def test_user_email_match(self, evaluator):
        assert evaluator.is_visible([], [], ["user@test.com"], _user(sub="user@test.com"))

    def test_role_case_insensitive(self, evaluator):
        assert evaluator.is_visible(["Sales"], [], [], _user(roles=["sales"]))
