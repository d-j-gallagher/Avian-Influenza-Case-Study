import io
import zipfile
from pathlib import Path

import streamlit as st

DOCX_PATH = Path("FETPF3.0_WS1_IG1_EN_Avian_Influenza_Instructor_Guide (6).docx")


def _extract_docx_text_fallback(docx_path: Path) -> str:
    """Extract text from a .docx file without third-party dependencies."""
    try:
        with zipfile.ZipFile(docx_path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (FileNotFoundError, KeyError, zipfile.BadZipFile) as exc:
        return f"Unable to read case study document: {exc}"

    xml_text = xml_bytes.decode("utf-8", errors="ignore")

    # Minimal XML-to-text extraction for WordprocessingML runs/paragraphs.
    text_parts = []
    current = io.StringIO()
    i = 0
    while i < len(xml_text):
        if xml_text.startswith("<w:t", i):
            start = xml_text.find(">", i)
            end = xml_text.find("</w:t>", start)
            if start == -1 or end == -1:
                break
            current.write(xml_text[start + 1 : end])
            i = end + len("</w:t>")
        elif xml_text.startswith("</w:p>", i):
            para = current.getvalue().strip()
            if para:
                text_parts.append(para)
            current = io.StringIO()
            i += len("</w:p>")
        else:
            i += 1

    if current.getvalue().strip():
        text_parts.append(current.getvalue().strip())

    return "\n\n".join(text_parts)


def load_case_study_text(docx_path: Path) -> str:
    """Load text from the case study docx using python-docx when available."""
    if not docx_path.exists():
        return (
            "Case study document not found. "
            f"Expected file at: {docx_path.resolve()}"
        )

    try:
        from docx import Document  # type: ignore

        document = Document(str(docx_path))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        if paragraphs:
            return "\n\n".join(paragraphs)
    except Exception:
        # Fall back to a lightweight parser if python-docx is unavailable.
        pass

    return _extract_docx_text_fallback(docx_path)


def main() -> None:
    st.set_page_config(page_title="Avian Influenza Case Study", layout="wide")
    st.title("Avian Influenza Case Study Q&A")
    st.caption("Type your answer below after reading the case study context.")

    case_study_text = load_case_study_text(DOCX_PATH)

    with st.expander("View case study content", expanded=False):
        st.text_area(
            "Case study text",
            value=case_study_text,
            height=350,
            disabled=True,
            key="case_study",
        )

    st.subheader("Your response")
    user_answer = st.text_input(
        "Enter your answer",
        placeholder="Type your answer here...",
        key="answer_input",
    )

    if st.button("Submit answer", type="primary"):
        if user_answer.strip():
            st.success("Answer received.")
            st.write("**You entered:**")
            st.write(user_answer)
        else:
            st.warning("Please type an answer before submitting.")


if __name__ == "__main__":
    main()
