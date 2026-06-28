"""
utils/rag.py — Chroma vectorstore builder & retriever for The Flame & Fork.

Source  : data/menu.pdf  (generated once by generate_menu_pdf.py)
Embedder: all-MiniLM-L6-v2 
Store   : vectorstore/chroma_db/
"""
import os
import logging
from functools import lru_cache

# ── Suppress noisy / broken telemetry & torch warnings BEFORE any imports ──────
# Disabling via env vars prevents the noisy error messages.
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"   # silences HF tokenizer fork warning

# Suppress the torch.classes/__path__ warning that fires when sentence-transformers
logging.getLogger("torch._classes").setLevel(logging.ERROR)
logging.getLogger("torch.classes").setLevel(logging.ERROR)

# broken capture() calls are silently ignored instead of printing a traceback on every startup.
try:
    import chromadb.telemetry.product.posthog as _chroma_ph  # type: ignore
    _chroma_ph.Posthog.capture = lambda self, *a, **kw: None  # type: ignore
except Exception:
    pass

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENU_PDF_PATH   = os.path.join(_BASE_DIR, "data", "menu.pdf")
CHROMA_DIR      = os.path.join(_BASE_DIR, "vectorstore", "chroma_db")
COLLECTION_NAME = "flame_fork_menu"


# ── Embedding model (cached at module level) ──────────────────────────────────
@lru_cache(maxsize=1)
def _get_embeddings() -> HuggingFaceEmbeddings:
    """Load embedding model once; subsequent calls return the cached instance."""
    print("[RAG] Loading embedding model (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    print("[RAG] Embedding model ready.")
    return embeddings


@lru_cache(maxsize=1)
def _load_vectorstore() -> Chroma:
    embeddings = _get_embeddings()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )


# ── Vectorstore ───────────────────────────────────────────────────────────────
def build_vectorstore(force_rebuild: bool = False) -> Chroma:
    """
    Load the Chroma store from disk, or build it from the menu PDF if absent.

    Parameters
    ----------
    force_rebuild : if True, delete the old store and re-embed from scratch.

    Returns
    -------
    A ready-to-use Chroma vectorstore instance.
    """
    # ── Return existing store ─────────────────────────────────────────────────
    if os.path.isdir(CHROMA_DIR) and not force_rebuild:
        return _load_vectorstore()

    if force_rebuild:
        _load_vectorstore.cache_clear()
        _get_embeddings.cache_clear()

    embeddings = _get_embeddings()

    # ── Build from menu PDF ───────────────────────────────────────────────────
    if not os.path.isfile(MENU_PDF_PATH):
        raise FileNotFoundError(
            f"Menu PDF not found at '{MENU_PDF_PATH}'. "
            "Run  python generate_menu_pdf.py  first."
        )

    print("[RAG] Building Chroma vectorstore from menu PDF...")
    loader = PyPDFLoader(MENU_PDF_PATH)
    pages  = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=60,
        separators=["\n\n", "\n", " ", ""],
    )
    docs = splitter.split_documents(pages)
    print(f"[RAG] {len(pages)} page(s) -> {len(docs)} chunks")

    os.makedirs(CHROMA_DIR, exist_ok=True)
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DIR,
    )
    print(f"[RAG] Vectorstore saved to {CHROMA_DIR}")
    _load_vectorstore.cache_clear()
    return vectorstore


def get_retriever(k: int = 6):
    """
    Return a LangChain retriever that fetches the top-k relevant menu chunks.

    Parameters
    ----------
    k : number of chunks to return per query (default 6)
    """
    vs = build_vectorstore()
    return vs.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
