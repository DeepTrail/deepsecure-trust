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
        }
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
        }
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
        }
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
        }
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
        }
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
        }
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
        }
    ),
]


# =============================================================================
# HubSpot Tools
# =============================================================================

HUBSPOT_TOOLS = [
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
        name="update_contact",
        description="Update an existing HubSpot contact",
        inputSchema={
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "HubSpot contact ID"
                },
                "properties": {
                    "type": "object",
                    "description": "Contact properties to update"
                }
            },
            "required": ["contact_id"]
        }
    ),
    CachedTool(
        name="list_contacts",
        description="List HubSpot contacts with optional filters",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum contacts to return",
                    "default": 20
                }
            }
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
    CachedTool(
        name="create_deal",
        description="Create a new deal in HubSpot",
        inputSchema={
            "type": "object",
            "properties": {
                "dealname": {
                    "type": "string",
                    "description": "Deal name"
                },
                "amount": {
                    "type": "number",
                    "description": "Deal amount"
                },
                "dealstage": {
                    "type": "string",
                    "description": "Deal stage"
                },
                "pipeline": {
                    "type": "string",
                    "description": "Pipeline ID"
                }
            },
            "required": ["dealname"]
        }
    ),
    CachedTool(
        name="update_deal",
        description="Update an existing HubSpot deal",
        inputSchema={
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "HubSpot deal ID"
                },
                "properties": {
                    "type": "object",
                    "description": "Deal properties to update"
                }
            },
            "required": ["deal_id"]
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
