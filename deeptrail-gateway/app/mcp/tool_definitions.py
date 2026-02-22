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
        }
    ),
    CachedTool(
        name="get_page",
        description="Get a specific Notion page by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "The Notion page ID (UUID format)"
                }
            },
            "required": ["page_id"]
        }
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
        }
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
        }
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
        }
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
        }
    ),
    CachedTool(
        name="post_message",
        description="Post a message to a Slack channel",
        inputSchema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel ID to post to"
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
        }
    ),
]


# =============================================================================
# HubSpot Tools
# =============================================================================

HUBSPOT_TOOLS = [
    CachedTool(
        name="search_contacts",
        description="Search HubSpot contacts by criteria",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (email, name, company)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    ),
    CachedTool(
        name="get_contact",
        description="Get a specific HubSpot contact by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "HubSpot contact ID"
                }
            },
            "required": ["contact_id"]
        }
    ),
    CachedTool(
        name="create_contact",
        description="Create a new contact in HubSpot",
        inputSchema={
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Contact email address"
                },
                "firstname": {
                    "type": "string",
                    "description": "First name"
                },
                "lastname": {
                    "type": "string",
                    "description": "Last name"
                },
                "company": {
                    "type": "string",
                    "description": "Company name"
                }
            },
            "required": ["email"]
        }
    ),
    CachedTool(
        name="list_deals",
        description="List HubSpot deals with optional filters",
        inputSchema={
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "description": "Filter by deal stage"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum deals to return",
                    "default": 20
                }
            }
        }
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
    cache.set_tools("hubspot", HUBSPOT_TOOLS)


def get_all_tool_definitions() -> dict[str, list[CachedTool]]:
    """
    Get all tool definitions as a dictionary.
    
    Returns:
        Dict mapping backend_id to list of tools
    """
    return {
        "notion": NOTION_TOOLS,
        "slack": SLACK_TOOLS,
        "hubspot": HUBSPOT_TOOLS,
    }
