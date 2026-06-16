"""
GitHub Client

Direct REST API client for GitHub API v3.

Tools:
- list_repos: List repositories for the authenticated user -> GET /user/repos
- read_repo: Get a repository by owner/name -> GET /repos/{owner}/{repo}
- list_issues: List issues for a repository -> GET /repos/{owner}/{repo}/issues
- create_issue: Create an issue -> POST /repos/{owner}/{repo}/issues
- list_pulls: List pull requests -> GET /repos/{owner}/{repo}/pulls
- create_pull: Create a pull request -> POST /repos/{owner}/{repo}/pulls
- list_commits: List commits -> GET /repos/{owner}/{repo}/commits
- read_org: Get an organization -> GET /orgs/{org}
- list_teams: List teams in an organization -> GET /orgs/{org}/teams
- read_user: Get a user by username -> GET /users/{username}

Usage:
    from app.backends.github_client import GitHubDirectClient

    client = GitHubDirectClient()
    result = await client.call_tool(
        "list_repos",
        {"per_page": 10},
        auth_token="ghp_xxx",
    )
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .base_mcp_client import ToolCallStatus, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class GitHubAPIConfig:
    """Configuration for GitHub API client."""
    base_url: str = "https://api.github.com"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


class GitHubDirectClient:
    """
    Direct GitHub REST API v3 client.

    Makes direct HTTP calls to GitHub's REST API, translating tool calls
    into appropriate API requests.
    """

    def __init__(self, config: GitHubAPIConfig | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                from app.core.config import get_settings
                settings = get_settings()
                self._config = GitHubAPIConfig(
                    base_url=settings.github.base_url,
                    timeout_seconds=settings.github.timeout_seconds,
                    retry_attempts=settings.github.retry_attempts,
                    retry_backoff_factor=settings.github.retry_backoff_factor,
                )
            except (ImportError, AttributeError):
                self._config = GitHubAPIConfig()

        self.base_url = self._config.base_url.rstrip("/")
        self.timeout = self._config.timeout_seconds

        logger.info("GitHubDirectClient initialized: base_url=%s", self.base_url)

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _transform_response(
        self,
        tool_name: str,
        response: httpx.Response,
        start_time: datetime,
    ) -> ToolResult:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", "Unknown error")
            except Exception:
                message = response.text[:500] if response.text else "Unknown error"

            error_message = message
            if response.status_code == 401:
                error_message = f"Unauthorized: {message}"
            elif response.status_code == 403:
                error_message = f"Forbidden: {message}"
            elif response.status_code == 404:
                error_message = f"Not found: {message}"
            elif response.status_code == 422:
                error_message = f"Validation error: {message}"
            elif response.status_code == 429:
                error_message = f"Rate limit exceeded: {message}"

            logger.warning(
                "GitHub API error for %s: %s (HTTP %d)",
                tool_name, error_message, response.status_code,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={"status_code": response.status_code, "error": message},
                duration_ms=duration_ms,
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        # GitHub list endpoints return JSON arrays. Wrap them in a dict
        # so the MCP content payload is always a record (required by the
        # MCP schema that Gemini CLI validates).
        if isinstance(data, list):
            data = {"items": data, "count": len(data)}

        logger.debug("GitHub API success for %s in %.1fms", tool_name, duration_ms)

        return ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": str(data)}],
            raw=data,
            duration_ms=duration_ms,
        )

    async def _request(
        self,
        method: str,
        path: str,
        auth_token: str | None,
        tool_name: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ToolResult:
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}{path}"
        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method, url,
                    params=params,
                    json=json_body,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response(tool_name, response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(ToolCallStatus.TIMEOUT, "Request timed out")
        except httpx.RequestError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, f"Request failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Dispatch
    # ─────────────────────────────────────────────────────────────────────────

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        tool_map = {
            "list_repos": self._call_list_repos,
            "read_repo": self._call_read_repo,
            "list_issues": self._call_list_issues,
            "create_issue": self._call_create_issue,
            "list_pulls": self._call_list_pulls,
            "create_pull": self._call_create_pull,
            "list_commits": self._call_list_commits,
            "read_org": self._call_read_org,
            "list_teams": self._call_list_teams,
            "read_user": self._call_read_user,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def _call_list_repos(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        params: dict[str, Any] = {}
        if args.get("per_page"):
            params["per_page"] = min(int(args["per_page"]), 100)
        if args.get("page"):
            params["page"] = int(args["page"])
        if args.get("sort"):
            params["sort"] = args["sort"]
        if args.get("type"):
            params["type"] = args["type"]
        return await self._request(
            "GET", "/user/repos", auth_token, "list_repos", params=params
        )

    async def _call_read_repo(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        if not owner or not repo:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "owner and repo are required"
            )
        return await self._request(
            "GET", f"/repos/{owner}/{repo}", auth_token, "read_repo"
        )

    async def _call_list_issues(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        if not owner or not repo:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "owner and repo are required"
            )
        params: dict[str, Any] = {}
        if args.get("state"):
            params["state"] = args["state"]
        if args.get("per_page"):
            params["per_page"] = min(int(args["per_page"]), 100)
        if args.get("page"):
            params["page"] = int(args["page"])
        if args.get("labels"):
            params["labels"] = args["labels"]
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/issues", auth_token, "list_issues",
            params=params,
        )

    async def _call_create_issue(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        title = args.get("title")
        if not owner or not repo or not title:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "owner, repo, and title are required"
            )
        body: dict[str, Any] = {"title": title}
        if args.get("body"):
            body["body"] = args["body"]
        if args.get("labels"):
            body["labels"] = args["labels"]
        if args.get("assignees"):
            body["assignees"] = args["assignees"]
        return await self._request(
            "POST", f"/repos/{owner}/{repo}/issues", auth_token, "create_issue",
            json_body=body,
        )

    async def _call_list_pulls(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        if not owner or not repo:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "owner and repo are required"
            )
        params: dict[str, Any] = {}
        if args.get("state"):
            params["state"] = args["state"]
        if args.get("per_page"):
            params["per_page"] = min(int(args["per_page"]), 100)
        if args.get("page"):
            params["page"] = int(args["page"])
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/pulls", auth_token, "list_pulls",
            params=params,
        )

    async def _call_create_pull(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        title = args.get("title")
        head = args.get("head")
        base = args.get("base")
        if not owner or not repo or not title or not head or not base:
            return ToolResult.from_error(
                ToolCallStatus.ERROR,
                "owner, repo, title, head, and base are required",
            )
        body: dict[str, Any] = {"title": title, "head": head, "base": base}
        if args.get("body"):
            body["body"] = args["body"]
        if args.get("draft") is not None:
            body["draft"] = args["draft"]
        return await self._request(
            "POST", f"/repos/{owner}/{repo}/pulls", auth_token, "create_pull",
            json_body=body,
        )

    async def _call_list_commits(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        owner = args.get("owner")
        repo = args.get("repo")
        if not owner or not repo:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "owner and repo are required"
            )
        params: dict[str, Any] = {}
        if args.get("sha"):
            params["sha"] = args["sha"]
        if args.get("per_page"):
            params["per_page"] = min(int(args["per_page"]), 100)
        if args.get("page"):
            params["page"] = int(args["page"])
        return await self._request(
            "GET", f"/repos/{owner}/{repo}/commits", auth_token, "list_commits",
            params=params,
        )

    async def _call_read_org(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        org = args.get("org")
        if not org:
            return ToolResult.from_error(ToolCallStatus.ERROR, "org is required")
        return await self._request(
            "GET", f"/orgs/{org}", auth_token, "read_org"
        )

    async def _call_list_teams(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        org = args.get("org")
        if not org:
            return ToolResult.from_error(ToolCallStatus.ERROR, "org is required")
        params: dict[str, Any] = {}
        if args.get("per_page"):
            params["per_page"] = min(int(args["per_page"]), 100)
        if args.get("page"):
            params["page"] = int(args["page"])
        return await self._request(
            "GET", f"/orgs/{org}/teams", auth_token, "list_teams",
            params=params,
        )

    async def _call_read_user(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        username = args.get("username")
        if not username:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "username is required"
            )
        return await self._request(
            "GET", f"/users/{username}", auth_token, "read_user"
        )
