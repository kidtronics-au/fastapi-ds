"""LangGraph RAG StateGraph: retrieve → chatbot."""

from typing import Callable

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from app.config import settings
from app.embedder import Embedder


class RAGState(MessagesState):
    context: list[str]
    sources: list[str]


def build_graph(embedder: Embedder, retrieve_fn: Callable) -> object:
    llm = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )

    memory = MemorySaver()

    async def retrieve(state: RAGState) -> dict:
        query = state["messages"][-1].content
        embedding = await embedder.embed_query(query)
        results = await retrieve_fn(embedding)
        return {
            "context": [r["content"] for r in results],
            "sources": [
                f"{r.get('document_title', '')} ({r.get('document_source', '')})"
                for r in results
            ],
        }

    async def chatbot(state: RAGState) -> dict:
        messages = list(state["messages"])
        context = state.get("context", [])
        if context:
            context_text = "\n\n".join(context)
            system = SystemMessage(
                content=(
                    "You are a helpful assistant. Use the following retrieved context "
                    "to answer the user's question. If the context is not relevant, "
                    "answer from your general knowledge.\n\n"
                    f"Context:\n{context_text}"
                )
            )
            messages = [system] + messages
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph_builder = StateGraph(RAGState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "chatbot")
    graph_builder.add_edge("chatbot", END)

    return graph_builder.compile(checkpointer=memory)
