import json
import re
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).parent
FLOW_PATH = BASE_DIR / "content" / "flows" / "part_b.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(rel_path: str) -> str:
    p = BASE_DIR / rel_path
    if not p.exists():
        return f"_Missing file: {p}_"
    return p.read_text(encoding="utf-8")


def extract_md_section(md_text: str, heading: str) -> str:
    """
    Extract content under a markdown heading (## or #),
    ignoring horizontal rules (---),
    and stopping only at the next same-level heading.
    """
    import re

    # Find the heading (case-insensitive)
    pattern = re.compile(rf"^(#{1,6})\s+{re.escape(heading)}\s*$",
                         re.MULTILINE | re.IGNORECASE)

    match = pattern.search(md_text)
    if not match:
        return f"_Section not found: {heading}_"

    level = len(match.group(1))  # number of #'s
    start = match.end()

    # Stop only at next heading of SAME level
    stop_pattern = re.compile(rf"^#{{{level}}}\s+.+$",
                              re.MULTILINE)

    next_match = stop_pattern.search(md_text, start)
    end = next_match.start() if next_match else len(md_text)

    section = md_text[start:end].strip()

    return section if section else "_(No content found in section)_"

def init_state(flow: dict):
    if "node_id" not in st.session_state:
        st.session_state.node_id = flow["start"]
    if "history" not in st.session_state:
        st.session_state.history = []
    if "answers" not in st.session_state:
        st.session_state.answers = {}


def goto(next_id: str):
    st.session_state.history.append(st.session_state.node_id)
    st.session_state.node_id = next_id
    st.rerun()


def go_back():
    if st.session_state.history:
        st.session_state.node_id = st.session_state.history.pop()
        st.rerun()


def sidebar(flow: dict):
    st.sidebar.header("Navigation")
    st.sidebar.write("Current:", st.session_state.node_id)
    st.sidebar.button("⬅ Back", on_click=go_back, disabled=not bool(st.session_state.history))

    with st.sidebar.expander("Jump to…"):
        for nid, node in flow["nodes"].items():
            if st.button(node.get("title", nid), key=f"jump_{nid}"):
                st.session_state.history.append(st.session_state.node_id)
                st.session_state.node_id = nid
                st.rerun()

    with st.sidebar.expander("Saved answers"):
        st.json(st.session_state.answers)


def main():
    st.set_page_config(page_title="Avian Influenza — Part B", layout="wide")

    flow = load_json(FLOW_PATH)
    init_state(flow)

    node_id = st.session_state.node_id
    node = flow["nodes"][node_id]

    st.title(flow["title"])
    st.subheader(node.get("title", node_id))

    sidebar(flow)

    md_text = read_text(node["md"]) if node.get("md") else ""

    t = node["type"]

    # ✅ Support read_section
    if t == "read_section":
        section_text = extract_md_section(md_text, node["section"])
        st.markdown(section_text)
        if node.get("next") and st.button("Next ➜"):
            goto(node["next"])

    # ✅ Support question_section
    elif t == "question_section":
        section_text = extract_md_section(md_text, node["section"])
        st.markdown(section_text)

        ans_key = node_id
        st.session_state.answers[ans_key] = st.text_area(
            "Your answer",
            value=st.session_state.answers.get(ans_key, ""),
            height=180
        )

        col1, col2 = st.columns([1, 1])
        col1.button("⬅ Back", on_click=go_back, disabled=not bool(st.session_state.history))
        if node.get("next") and col2.button("Continue ➜"):
            goto(node["next"])

    elif t == "debrief":
        st.write("You finished Part B.")
        st.markdown("---")
        st.json(st.session_state.answers)

        col1, col2 = st.columns([1, 1])
        col1.button("⬅ Back", on_click=go_back, disabled=not bool(st.session_state.history))
        if col2.button("Restart"):
            st.session_state.clear()
            st.rerun()

    else:
        st.error(f"Unsupported node type: {t}")


if __name__ == "__main__":
    main()