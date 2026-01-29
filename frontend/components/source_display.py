"""Source documents display component for RAG responses."""
import streamlit as st
from typing import List, Dict


def render_sources(sources: List[Dict]):
    """Render source documents from RAG retrieval."""
    if not sources:
        return

    with st.expander("View Sources", expanded=False):
        st.subheader("Source Documents")

        for i, source in enumerate(sources, 1):
            doc_name = source.get("document", source.get("source", f"Source {i}"))
            chunk_text = source.get("content", source.get("text", ""))
            score = source.get("score", source.get("similarity"))

            # Source header with score
            header = f"**{i}. {doc_name}**"
            if score is not None:
                header += f" (relevance: {score:.2f})"

            st.markdown(header)

            # Show chunk preview
            if chunk_text:
                # Truncate if too long
                preview = chunk_text[:500]
                if len(chunk_text) > 500:
                    preview += "..."

                st.markdown(
                    f'<div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-size: 0.9em; margin-bottom: 10px;">{preview}</div>',
                    unsafe_allow_html=True
                )

            # Metadata if available
            metadata = source.get("metadata", {})
            if metadata:
                metadata_items = []
                if metadata.get("section"):
                    metadata_items.append(f"Section: {metadata['section']}")
                if metadata.get("page"):
                    metadata_items.append(f"Page: {metadata['page']}")
                if metadata_items:
                    st.caption(" | ".join(metadata_items))

            if i < len(sources):
                st.divider()
