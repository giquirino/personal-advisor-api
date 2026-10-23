"""Expose the existing financial tools to MCP clients over stdio."""

from typing import Annotated

try:
    from mcp.server import MCPServer
except ImportError:  # MCP SDK 1.x installed in an existing environment
    from mcp.server.fastmcp import FastMCP as MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.tools import financeiro

mcp = MCPServer("assessor-financeiro")
READ = ToolAnnotations(readOnlyHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@mcp.tool(annotations=READ)
def query_transactions(
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    date: str | None = None,
    type_filter: str | None = None,
) -> dict:
    """List recent transactions, optionally filtered by date and type."""
    return financeiro.query_transactions.invoke(
        {"limit": limit, "date": date, "type_filter": type_filter}
    )


@mcp.tool(annotations=READ)
def total_balance() -> dict:
    """Return income minus expenses across the full history."""
    return financeiro.total_balance.invoke({})


@mcp.tool(annotations=READ)
def daily_balance(date: Annotated[str, Field(description="Date as YYYY-MM-DD")]) -> dict:
    """Return income minus expenses on one day."""
    return financeiro.daily_balance.invoke({"date": date})


@mcp.tool(annotations=WRITE)
def add_transaction(
    amount: Annotated[float, Field(gt=0)],
    source_text: str,
    type_name: str,
    category_name: str | None = None,
    occurred_at: str | None = None,
    description: str | None = None,
    payment_method: str | None = None,
) -> dict:
    """Record an income, expense, or transfer transaction."""
    return financeiro.add_transaction.invoke(
        {
            "amount": amount,
            "source_text": source_text,
            "type_name": type_name,
            "category_name": category_name,
            "occurred_at": occurred_at,
            "description": description,
            "payment_method": payment_method,
        }
    )


@mcp.tool(annotations=WRITE)
def update_transaction(
    id: int | None = None,
    match_text: str | None = None,
    date_local: str | None = None,
    amount: float | None = None,
    type_name: str | None = None,
    category_name: str | None = None,
    description: str | None = None,
    payment_method: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    """Update a transaction by ID or by matching text and local date."""
    return financeiro.update_transaction.invoke(
        {
            "id": id,
            "match_text": match_text,
            "date_local": date_local,
            "amount": amount,
            "type_name": type_name,
            "category_name": category_name,
            "description": description,
            "payment_method": payment_method,
            "occurred_at": occurred_at,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
