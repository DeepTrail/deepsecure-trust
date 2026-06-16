"""
MCP Tool Definitions for Virtual MCP Server.

This module defines the complete tool schemas for all supported backends.
These definitions are used to populate the tool cache and provide proper
descriptions and input schemas for the tools/list endpoint.

Each backend has a list of tools with:
- name: Tool name (without namespace prefix)
- description: Human-readable description
- inputSchema: JSON Schema for tool parameters
"""

from .tool_cache import CachedTool, ToolCache


# =============================================================================
# Notion Tools
# =============================================================================

NOTION_TOOLS = [
    CachedTool(
        name="search_pages",
        description="Search for pages in Notion workspace",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10
                },
                "filter": {
                    "type": "object",
                    "description": "Optional filter criteria",
                    "properties": {
                        "property": {"type": "string"},
                        "value": {"type": "string"}
                    }
                }
            },
            "required": ["query"]
        },
        permission="notion:pages:search",
    ),
    CachedTool(
        name="read_page",
        description="Read a specific Notion page by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID (UUID format)"
                }
            },
            "required": ["page_id"]
        },
        permission="notion:pages:read",
    ),
    CachedTool(
        name="get_page_content",
        description="Get the content blocks of a Notion page (paragraphs, headings, lists)",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID (UUID format)"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Max blocks to return (1-100)",
                    "default": 100
                }
            },
            "required": ["page_id"]
        },
        permission="notion:blocks:read",
    ),
    CachedTool(
        name="create_page",
        description="Create a new page in Notion",
        inputSchema={
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "Parent page or database ID"
                },
                "title": {
                    "type": "string",
                    "description": "Page title"
                },
                "content": {
                    "type": "string",
                    "description": "Page content in markdown format"
                }
            },
            "required": ["parent_id", "title"]
        },
        permission="notion:pages:create",
    ),
    CachedTool(
        name="update_page",
        description="Update an existing Notion page",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID to update"
                },
                "properties": {
                    "type": "object",
                    "description": "Page properties to update"
                }
            },
            "required": ["page_id"]
        },
        permission="notion:pages:update",
    ),
    CachedTool(
        name="delete_page",
        description="Archive/delete a Notion page",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID to delete"
                }
            },
            "required": ["page_id"]
        },
        permission="notion:pages:delete",
    ),
    CachedTool(
        name="list_databases",
        description="List all databases in Notion workspace",
        inputSchema={
            "type": "object",
            "properties": {
                "page_size": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 10
                }
            }
        },
        permission="notion:databases:list",
    ),
    CachedTool(
        name="query_database",
        description="Query a Notion database with filters",
        inputSchema={
            "type": "object",
            "properties": {
                "database_id": {
                    "type": "string",
                    "description": "The Notion database ID"
                },
                "filter": {
                    "type": "object",
                    "description": "Filter conditions"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 100
                }
            },
            "required": ["database_id"]
        },
        permission="notion:databases:query",
    ),
]


# =============================================================================
# Slack Tools
# =============================================================================

SLACK_TOOLS = [
    CachedTool(
        name="search_messages",
        description="Search Slack messages across channels",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional channel ID to search in"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 20
                }
            },
            "required": ["query"]
        },
        permission="slack:messages:search",
    ),
    CachedTool(
        name="send_message",
        description="Send a message to a Slack channel",
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel ID to send message to"
                },
                "text": {
                    "type": "string",
                    "description": "Message text"
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Optional thread timestamp for replies"
                }
            },
            "required": ["channel", "text"]
        },
        permission="slack:messages:send",
    ),
    CachedTool(
        name="list_channels",
        description="List available Slack channels",
        inputSchema={
            "type": "object",
            "properties": {
                "types": {
                    "type": "string",
                    "description": "Channel types (public_channel, private_channel)",
                    "default": "public_channel"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of channels to return",
                    "default": 100
                }
            }
        },
        permission="slack:channels:list",
    ),
    CachedTool(
        name="get_channel_history",
        description="Get recent messages from a Slack channel",
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel ID (e.g., C090C60ADU7)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of messages to return (1-100)",
                    "default": 10
                }
            },
            "required": ["channel"]
        },
        permission="slack:channels:history",
    ),
    CachedTool(
        name="join_channel",
        description="Join a Slack channel",
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel ID to join"
                }
            },
            "required": ["channel"]
        },
        permission="slack:channels:join",
    ),
    CachedTool(
        name="post_reaction",
        description="Add a reaction emoji to a message",
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel containing the message"
                },
                "timestamp": {
                    "type": "string",
                    "description": "Message timestamp"
                },
                "name": {
                    "type": "string",
                    "description": "Reaction emoji name (without colons)"
                }
            },
            "required": ["channel", "timestamp", "name"]
        },
        permission="slack:reactions:write",
    ),
    CachedTool(
        name="list_users",
        description="List users in Slack workspace",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum users to return",
                    "default": 100
                }
            }
        },
        permission="slack:users:list",
    ),
    CachedTool(
        name="search_users",
        description="Search for users in Slack workspace by name or email",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (name or email)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum users to return",
                    "default": 20
                }
            },
            "required": ["query"]
        },
        permission="slack:users:search",
    ),
]


# =============================================================================
# Google Drive Tools
# =============================================================================

GDRIVE_TOOLS = [
    CachedTool(
        name="search_files",
        description="Search for files in Google Drive",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string (supports Google Drive query syntax)"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10
                }
            },
            "required": ["query"]
        },
        permission="gdrive:files:search",
    ),
    CachedTool(
        name="read_file",
        description="Read file content by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The Google Drive file ID"
                }
            },
            "required": ["file_id"]
        },
        permission="gdrive:files:read",
    ),
    CachedTool(
        name="list_files",
        description="List files in a folder",
        inputSchema={
            "type": "object",
            "properties": {
                "folder_id": {
                    "type": "string",
                    "description": "Folder ID to list files from (omit for root)"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 10
                }
            }
        },
        permission="gdrive:files:list",
    ),
    CachedTool(
        name="get_file_metadata",
        description="Get metadata for a file",
        inputSchema={
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The Google Drive file ID"
                }
            },
            "required": ["file_id"]
        },
        permission="gdrive:files:metadata",
    ),
]


# =============================================================================
# Google Calendar Tools
# =============================================================================

GCALENDAR_TOOLS = [
    CachedTool(
        name="list_calendars",
        description="List available calendars",
        inputSchema={
            "type": "object",
            "properties": {
                "page_size": {
                    "type": "integer",
                    "description": "Maximum number of calendars to return",
                    "default": 10
                }
            }
        },
        permission="gcalendar:calendars:list",
    ),
    CachedTool(
        name="list_events",
        description="List events from a calendar",
        inputSchema={
            "type": "object",
            "properties": {
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (defaults to primary calendar)",
                    "default": "primary"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return",
                    "default": 10
                },
                "time_min": {
                    "type": "string",
                    "description": "Lower bound for event start time (ISO 8601 format)"
                },
                "time_max": {
                    "type": "string",
                    "description": "Upper bound for event start time (ISO 8601 format)"
                }
            }
        },
        permission="gcalendar:events:list",
    ),
    CachedTool(
        name="read_event",
        description="Read a specific calendar event",
        inputSchema={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The calendar event ID"
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (defaults to primary calendar)",
                    "default": "primary"
                }
            },
            "required": ["event_id"]
        },
        permission="gcalendar:events:read",
    ),
    CachedTool(
        name="search_events",
        description="Search events across calendars",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search query"
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (defaults to primary calendar)",
                    "default": "primary"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to return",
                    "default": 10
                }
            },
            "required": ["query"]
        },
        permission="gcalendar:events:search",
    ),
]


# =============================================================================
# Gmail Tools
# =============================================================================

GMAIL_TOOLS = [
    CachedTool(
        name="list_messages",
        description="List messages in mailbox",
        inputSchema={
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of messages to return",
                    "default": 10
                },
                "label_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by label IDs (e.g. INBOX, UNREAD)"
                }
            }
        },
        permission="gmail:messages:list",
    ),
    CachedTool(
        name="read_message",
        description="Read a specific email message",
        inputSchema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "The Gmail message ID"
                },
                "format": {
                    "type": "string",
                    "description": "Response format: full, metadata, minimal, or raw",
                    "default": "full"
                }
            },
            "required": ["message_id"]
        },
        permission="gmail:messages:read",
    ),
    CachedTool(
        name="search_messages",
        description="Search emails by query",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g. from:alice subject:meeting)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of messages to return",
                    "default": 10
                }
            },
            "required": ["query"]
        },
        permission="gmail:messages:search",
    ),
    CachedTool(
        name="list_labels",
        description="List Gmail labels",
        inputSchema={
            "type": "object",
            "properties": {}
        },
        permission="gmail:labels:list",
    ),
]


# =============================================================================
# GitHub Tools
# =============================================================================

GITHUB_TOOLS = [
    CachedTool(
        name="list_repos",
        description="List repositories for the authenticated GitHub user",
        inputSchema={
            "type": "object",
            "properties": {
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (max 100)",
                    "default": 30
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination",
                    "default": 1
                },
                "sort": {
                    "type": "string",
                    "description": "Sort field (created, updated, pushed, full_name)",
                    "enum": ["created", "updated", "pushed", "full_name"]
                },
                "type": {
                    "type": "string",
                    "description": "Filter by repo type (all, owner, public, private, member)",
                    "enum": ["all", "owner", "public", "private", "member"]
                }
            }
        },
        permission="github:repos:list",
    ),
    CachedTool(
        name="read_repo",
        description="Get details of a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (user or org)"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                }
            },
            "required": ["owner", "repo"]
        },
        permission="github:repos:read",
    ),
    CachedTool(
        name="list_issues",
        description="List issues for a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "state": {
                    "type": "string",
                    "description": "Filter by state (open, closed, all)",
                    "default": "open",
                    "enum": ["open", "closed", "all"]
                },
                "labels": {
                    "type": "string",
                    "description": "Comma-separated list of label names"
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (max 100)",
                    "default": 30
                },
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                }
            },
            "required": ["owner", "repo"]
        },
        permission="github:issues:read",
    ),
    CachedTool(
        name="create_issue",
        description="Create a new issue in a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "title": {
                    "type": "string",
                    "description": "Issue title"
                },
                "body": {
                    "type": "string",
                    "description": "Issue body (markdown)"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to apply"
                },
                "assignees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Usernames to assign"
                }
            },
            "required": ["owner", "repo", "title"]
        },
        permission="github:issues:create",
    ),
    CachedTool(
        name="list_pulls",
        description="List pull requests for a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "state": {
                    "type": "string",
                    "description": "Filter by state (open, closed, all)",
                    "default": "open",
                    "enum": ["open", "closed", "all"]
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (max 100)",
                    "default": 30
                },
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                }
            },
            "required": ["owner", "repo"]
        },
        permission="github:pulls:read",
    ),
    CachedTool(
        name="create_pull",
        description="Create a pull request in a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "title": {
                    "type": "string",
                    "description": "Pull request title"
                },
                "head": {
                    "type": "string",
                    "description": "Branch containing changes"
                },
                "base": {
                    "type": "string",
                    "description": "Branch to merge into"
                },
                "body": {
                    "type": "string",
                    "description": "Pull request body (markdown)"
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft PR",
                    "default": False
                }
            },
            "required": ["owner", "repo", "title", "head", "base"]
        },
        permission="github:pulls:create",
    ),
    CachedTool(
        name="list_commits",
        description="List commits for a GitHub repository",
        inputSchema={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner"
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name"
                },
                "sha": {
                    "type": "string",
                    "description": "Branch name or commit SHA to list from"
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (max 100)",
                    "default": 30
                },
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                }
            },
            "required": ["owner", "repo"]
        },
        permission="github:commits:read",
    ),
    CachedTool(
        name="read_org",
        description="Get details of a GitHub organization",
        inputSchema={
            "type": "object",
            "properties": {
                "org": {
                    "type": "string",
                    "description": "Organization name"
                }
            },
            "required": ["org"]
        },
        permission="github:orgs:read",
    ),
    CachedTool(
        name="list_teams",
        description="List teams in a GitHub organization",
        inputSchema={
            "type": "object",
            "properties": {
                "org": {
                    "type": "string",
                    "description": "Organization name"
                },
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (max 100)",
                    "default": 30
                },
                "page": {
                    "type": "integer",
                    "description": "Page number",
                    "default": 1
                }
            },
            "required": ["org"]
        },
        permission="github:teams:list",
    ),
    CachedTool(
        name="read_user",
        description="Get a GitHub user's public profile",
        inputSchema={
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "GitHub username"
                }
            },
            "required": ["username"]
        },
        permission="github:users:read",
    ),
]


# =============================================================================
# Cache Population
# =============================================================================

def populate_tool_cache(cache: ToolCache) -> None:
    """
    Populate the tool cache with all backend tool definitions.
    
    This should be called during app initialization to ensure
    proper tool schemas are available for tools/list responses.
    
    Args:
        cache: The ToolCache instance to populate
    """
    cache.set_tools("notion", NOTION_TOOLS)
    cache.set_tools("slack", SLACK_TOOLS)
    cache.set_tools("github", GITHUB_TOOLS)
    cache.set_tools("gdrive", GDRIVE_TOOLS)
    cache.set_tools("gcalendar", GCALENDAR_TOOLS)
    cache.set_tools("gmail", GMAIL_TOOLS)


def get_all_tool_definitions() -> dict[str, list[CachedTool]]:
    """
    Get all tool definitions as a dictionary.
    
    Returns:
        Dict mapping backend_id to list of tools
    """
    return {
        "notion": NOTION_TOOLS,
        "slack": SLACK_TOOLS,
        "gdrive": GDRIVE_TOOLS,
        "gcalendar": GCALENDAR_TOOLS,
        "gmail": GMAIL_TOOLS,
        "github": GITHUB_TOOLS,
    }
