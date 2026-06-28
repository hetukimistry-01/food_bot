"""
app.py — AI Food Ordering Chatbot.
"""
import logging
import re
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="The Flame & Fork",
    page_icon="🍴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #FFF8F5; }
    [data-testid="stSidebar"] { background-color: #1C1C1C; color: #F5F5F5; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label { color: #F5F5F5 !important; }
    .user-bubble {
        background: #B5451B; color: white;
        border-radius: 18px 18px 4px 18px;
        padding: 10px 16px; margin: 6px 0;
        max-width: 80%; margin-left: auto; text-align: right;
    }
    .bot-bubble {
        background: #FFFFFF; color: #1C1C1C;
        border: 1px solid #E0C8BF;
        border-radius: 18px 18px 18px 4px;
        padding: 10px 16px; margin: 6px 0;
        max-width: 85%; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .hero-title { color: #B5451B; font-size: 2rem; font-weight: 800; }
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #E0C8BF;
        border-radius: 10px; padding: 12px;
    }
    .stTextInput > div > div > input { border-radius: 24px; border: 1.5px solid #B5451B; }
    .stButton > button {
        border-radius: 24px; background: #B5451B;
        color: white; border: none; font-weight: 600;
    }
    .stButton > button:hover { background: #8C3415; color: white; }
    .token-badge {
        font-size: 0.72rem; color: #888; text-align: right;
        padding: 2px 8px; margin-top: -4px;
    }
</style>
""", unsafe_allow_html=True)


# ── Lazy init ─────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="🍳 Firing up the kitchen… hang tight, first run only!")
def _init_rag():
    from utils.database import init_db
    from utils.rag import build_vectorstore
    init_db()
    build_vectorstore()


def _init_agent():
    from utils.agent import build_agent
    return build_agent()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## The Flame & Fork")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["💬 Chat & Order", "📊 Sales Dashboard", "📋 All Orders"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("""
**Quick tips:**
- *"Show me the menu"*
- *"I'd like 2 Margherita pizzas and an Oreo Shake"*
- *"What's in the pesto pasta?"*
- *"Get order #3"*
""")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.token_count = 0
        st.rerun()

    st.markdown("---")
    # Token usage display
    used = st.session_state.get("token_count", 0)
    limit = 6_000          # conservative daily free-tier budget shown to user
    pct   = min(int(used / limit * 100), 100) if limit else 0
    st.markdown(f"**Token usage** (session): `{used:,}` / ~`{limit:,}`")
    st.progress(pct)
    if pct >= 90:
        st.warning("⚠️ Approaching token limit. Clear chat to reset session context.")


# ════════════════════════════════════════════════════════════════════════════
#  PAGE: Chat & Order
# ════════════════════════════════════════════════════════════════════════════
if page == "💬 Chat & Order":
    st.markdown('<p class="hero-title">🍴 The Flame & Fork Chatbot</p>', unsafe_allow_html=True)
    st.caption("Your AI-powered food ordering assistant. Ask me about the menu or place an order!")

    _init_rag()
    agent = _init_agent()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Welcome to **The Flame & Fork**! I'm Flamey, your ordering assistant.\n\n"
                    "I can help you explore our menu, answer questions about dishes, or take your order. "
                    "What can I get started for you? 🍔🍕🌮"
                ),
            }
        ]
    if "token_count" not in st.session_state:
        st.session_state.token_count = 0

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="user-bubble">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bot-bubble">🔥 {msg["content"]}</div>', unsafe_allow_html=True)

    # ── Input row ─────────────────────────────────────────────────────────────
    with st.form(key="chat_form", clear_on_submit=True):
        col_input, col_send = st.columns([8, 1])
        with col_input:
            user_input = st.text_input(
                "Your message",
                key="user_input",
                placeholder="e.g. 'I'd like a veg Biryani and a mango shake.'",
                label_visibility="collapsed",
            )
        with col_send:
            send = st.form_submit_button("Send ➤")

    if send and user_input.strip():
        user_text = user_input.strip()
        st.session_state.messages.append({"role": "user", "content": user_text})

        with st.spinner("Flamey is thinking… 🍳"):
            from langchain_core.messages import HumanMessage, AIMessage
            from utils.agent import _trim_history

            # Build trimmed history (excludes the message we just added)
            raw_history = []
            for m in st.session_state.messages[:-1]:
                if m["role"] == "user":
                    raw_history.append(HumanMessage(content=m["content"]))
                else:
                    raw_history.append(AIMessage(content=m["content"]))

            lc_history = _trim_history(raw_history)

            try:
                response = agent.invoke({
                    "input":        user_text,
                    "chat_history": lc_history,
                })
                answer = response.get("output", "Sorry, I couldn't process that.")

                # Track approximate token usage from Groq usage metadata if available
                usage = getattr(response, "get", lambda k, d=None: None)("usage_metadata")
                if usage and isinstance(usage, dict):
                    st.session_state.token_count += usage.get("total_tokens", 0)
                else:
                    # Rough estimate: ~1.3 tokens per character for input+output
                    st.session_state.token_count += int(
                        (len(user_text) + len(answer)) * 1.3 / 4
                    )

            except Exception as exc:
                exc_str = str(exc)
                logging.error("[Flamey] Agent exception: %s", exc_str, exc_info=True)

                if "429" in exc_str or "rate limit" in exc_str.lower():
                    match = re.search(
                        r"try again in (\d+m\d+\.?\d*s|\d+\.?\d*s|\d+m)",
                        exc_str, re.IGNORECASE
                    )
                    wait_hint = (
                        f" Please wait **{match.group(1)}** and try again."
                        if match else " Please try again in a few minutes."
                    )
                    answer = (
                        "⏳ **Rate limit reached.** The AI model is temporarily over its daily token limit.\n\n"
                        + wait_hint
                        + "\n\n> 💡 *Tip: Upgrade at [console.groq.com/settings/billing](https://console.groq.com/settings/billing) for more capacity.*"
                    )
                else:
                    answer = f"⚠️ Error: {exc}"

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
#  PAGE: Sales Dashboard
# ════════════════════════════════════════════════════════════════════════════
elif page == "📊 Sales Dashboard":
    st.markdown('<p class="hero-title">📊 Sales Dashboard</p>', unsafe_allow_html=True)
    st.caption("Real-time insights from the orders database.")

    from utils.database import init_db, get_sales_summary
    import pandas as pd

    init_db()
    summary = get_sales_summary()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Orders",   summary["total_orders"])
    c2.metric("Total Revenue",  f"₹{summary['total_revenue']:.2f}")
    avg = (summary["total_revenue"] / summary["total_orders"]) if summary["total_orders"] else 0
    c3.metric("Avg Order Value", f"₹{avg:.2f}")

    st.markdown("---")
    st.subheader("🏆 Best-Selling Items")

    if summary["best_sellers"]:
        df = pd.DataFrame(summary["best_sellers"])
        df.columns = ["Item", "Units Sold", "Revenue (₹)"]
        df["Revenue (₹)"] = df["Revenue (₹)"].round(2)

        col_chart, col_table = st.columns([1, 1])
        with col_chart:
            st.bar_chart(df.set_index("Item")["Units Sold"])
        with col_table:
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No orders yet. Start chatting to place some orders! 🍔")


# ════════════════════════════════════════════════════════════════════════════
#  PAGE: All Orders
# ════════════════════════════════════════════════════════════════════════════
elif page == "📋 All Orders":
    st.markdown('<p class="hero-title">📋 All Orders</p>', unsafe_allow_html=True)

    from utils.database import init_db, get_all_orders
    import pandas as pd

    init_db()
    orders = get_all_orders()

    if not orders:
        st.info("No orders placed yet. Head to the chat to start ordering!")
    else:
        rows = []
        for o in orders:
            item_summary = ", ".join(
                f"{it['item_name']} x{it['quantity']}" for it in o["items"]
            )
            rows.append({
                "Order #":    o["id"],
                "Customer":   o["customer"],
                "Items":      item_summary,
                "Total (₹)":  o["total"],
                "Status":     o["status"],
                "Placed At":  o["created_at"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
