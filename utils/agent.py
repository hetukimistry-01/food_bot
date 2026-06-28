"""
utils/agent.py — LangChain AgentExecutor for The Flame & Fork.

Wires together:
  • Groq LLM
  • RAG tool  (menu_search  — Chroma + HuggingFace embeddings)
  • DB tools  (place_order, get_order — custom BaseTool subclasses)
  • Multi-turn chat history via MessagesPlaceholder
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from tools.order_tool import PlaceOrderTool, GetOrderTool
from utils.rag import get_retriever


# ── Trimming helper ───────────────────────────────────────────────────────────
_MAX_HISTORY_TURNS = 6   # keep last 6 human+AI pairs → 12 messages max

def _trim_history(history: list[BaseMessage]) -> list[BaseMessage]:
    """Return only the last _MAX_HISTORY_TURNS pairs to limit context size."""
    max_msgs = _MAX_HISTORY_TURNS * 2
    return history[-max_msgs:] if len(history) > max_msgs else history


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """You are Flamey, the AI ordering assistant for The Flame & Fork restaurant.

TOOLS — when to use each:
• menu_search  → call whenever the customer asks about dishes, prices, ingredients, or menu, or mentions any food item. Do NOT call for greetings, confirmations, or order status.
• place_order  → call ONLY after the customer says YES/confirm AND you already have their name.
• get_order    → only when the customer asks about a previous order by ID.

═══════════════════════════════════════════════════════
STRICT ORDERING FLOW — follow these steps in order, never skip:
═══════════════════════════════════════════════════════

STEP 1 — SHOW MENU / VERIFY ITEMS:
  • When the customer asks for the menu OR mentions any food item, call menu_search immediately.
  • Present items in this format:
      Here's what we have:
      Margherita Pizza — ₹249
      Paneer Tikka — ₹299
  • GENERIC / SHORT CATEGORY NAMES (e.g. "pizza", "pasta", "burger", "shake", "dessert"):
    - If the customer says only a category name without specifying a variety, list ALL available varieties
      of that category from the search results with their prices in ₹. Then ask: "Which one would you like?" — do NOT assume or pick a variety for them.
    - Only proceed to build an order once the customer names a specific dish.
    - Examples of generic inputs: "pizza", "pasta", "I want burger", "give me a shake", "order biryani"
  • SPECIFIC DISH NAMES (e.g. "Margherita Pizza", "Pesto Pasta"):
    - Confirm the item and price in ₹, then ask: "Would you like anything else, or are you ready to order?"
  Do NOT ask for their name at this stage.

STEP 2 — BUILD ORDER SUMMARY:
  • Once the customer specifies their final items, show a clear order summary with prices in ₹.
  • Ask: "Are you ready to place this order?"
  Do NOT ask for their name at this stage yet.

STEP 3 — COLLECT CUSTOMER NAME (only when customer is ready to place the order):
  • Ask: "May I have your name please?"

STEP 4 — CONFIRM:
  • Once you have the name, echo the full order with each item's price in ₹ and the total, then ask:
      "Shall I confirm this order for [Name]?"

STEP 5 — PLACE ORDER:
  • Only on explicit YES / confirm / go ahead → call place_order once.
  • Always Report back the Order number # and total in ₹ after placing the order.

═══════════════════════════════════════════════════════
CORRECTION / CANCELLATION RULES:
═══════════════════════════════════════════════════════
  • If the customer disputes or cancels at the confirmation step:
    - Do NOT restart from Step 1 and do NOT re-ask for the name.
    - Say: "I'm sorry! What would you like to change?"
    - Update the order (call menu_search if needed for new items) and return to STEP 4.
  • If the customer asks for the menu at ANY point (even mid-order):
    - Call menu_search and display results — do NOT ask for their name as a response.

═══════════════════════════════════════════════════════
PRICE RULES — CRITICAL:
═══════════════════════════════════════════════════════
  • ALWAYS use ₹ (Indian Rupee symbol) — NEVER use $ or any other currency symbol.
  • NEVER invent or estimate prices. Only use prices returned directly by menu_search.
  • If an item is not found, say so clearly and suggest similar items via menu_search.

GENERAL RULES:
  • Strictly DO NOT give any items outside of menu. ONLY give the answer based on provided context. Never add items from memory or model knowledge.
  • Never call menu_search more than once per user message.
  • Never place an order without a confirmed customer name (never use "Guest").
  • Be warm, helpful, and concise. Light emoji are welcome 🍔🍕🌮."""


# ── Menu search tool with per-session cache ───────────────────────────────────
class _MenuSearchInput(BaseModel):
    query: str = Field(description="What to look up in the menu.")


class MenuSearchTool(BaseTool):
    name: str = "menu_search"
    description: str = (
        "Search the restaurant menu for items, prices, descriptions, and ingredients. "
        "Call ONLY when the customer asks about food — never for confirmations or greetings."
    )
    args_schema: type[BaseModel] = _MenuSearchInput
    _cache: dict[str, str] = {}   # simple in-memory cache per tool instance

    def _run(self, query: str) -> str:
        key = query.lower().strip()
        if key in self._cache:
            return self._cache[key]

        q_lower = key
        menu_keywords = ["menu", "all items", "list", "entire", "whole", "full", "dishes", "options", "available"]
        k = 8 if any(w in q_lower for w in menu_keywords) else 4

        retriever = get_retriever(k=k)
        docs = retriever.invoke(query) if hasattr(retriever, "invoke") else retriever.get_relevant_documents(query)
        result = "\n\n".join(doc.page_content for doc in docs)
        self._cache[key] = result
        return result

    async def _arun(self, query: str) -> str:
        return self._run(query)


# ── Agent factory ─────────────────────────────────────────────────────────────
def build_agent() -> AgentExecutor:
    """
    Build and return a ready-to-use AgentExecutor.
    GROQ_API_KEY must be set in the environment before calling this.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. Add it to your .env file or enter it in the sidebar."
        )

    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=768,
    )

    tools: list[BaseTool] = [
        MenuSearchTool(),
        PlaceOrderTool(),
        GetOrderTool(),
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system",  _SYSTEM),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human",   "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=6,
        handle_parsing_errors=True,
        return_intermediate_steps=False,
    )
