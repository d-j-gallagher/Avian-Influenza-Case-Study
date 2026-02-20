import json
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).parent
FLOW_PATH = BASE_DIR / "content" / "flows" / "part_a.json"

def read_text(rel_path: str) -> str:
    p = Path(rel_path)
    if not p.is_absolute():
        p = BASE_DIR / rel_path
    if not p.exists():
        return f"_Missing file: {p}_"
    return p.read_text(encoding="utf-8")

def load_flow():
    with open(FLOW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def init_state(flow):
    if "node_id" not in st.session_state:
        st.session_state.node_id = flow["start"]
    if "score" not in st.session_state:
        st.session_state.score = 0
    if "history" not in st.session_state:
        st.session_state.history = []

def goto(next_id):
    st.session_state.history.append(st.session_state.node_id)
    st.session_state.node_id = next_id
    st.rerun()

def render_read(node):
    if node.get("md"):
        st.markdown(read_text(node["md"]))
    if node.get("next"):
        if st.button("Next"):
            goto(node["next"])

def render_short_answer(node):
    st.write(node.get("prompt",""))
    ans_key = f"ans_{st.session_state.node_id}"
    st.text_area("Your answer", key=ans_key, height=140)

    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Submit"):
            st.session_state[f"submitted_{st.session_state.node_id}"] = True
            st.rerun()

    submitted = st.session_state.get(f"submitted_{st.session_state.node_id}", False)
    if submitted:
        st.success("Answer saved.")
        if "answer_guidance" in node:
            st.markdown("**Suggested answer / guidance:**")
            for line in node["answer_guidance"]:
                st.write(f"- {line}")
        if "answer_guidance_md" in node:
            st.markdown("**Reference guidance:**")
            st.markdown(read_text(node["answer_guidance_md"]))
        if node.get("next"):
            if st.button("Continue"):
                goto(node["next"])

    with col2:
        st.markdown("**Status**")
        st.write({"score": st.session_state.score, "node": st.session_state.node_id})

def render_table(node):
    if node.get("md"):
        st.markdown(read_text(node["md"]))
    if node.get("csv"):
        p = BASE_DIR / node["csv"]
        if p.exists():
            df = pd.read_csv(p)
            st.dataframe(df, use_container_width=True)
        else:
            st.error(f"Missing CSV: {p}")
    if node.get("next"):
        if st.button("Next"):
            goto(node["next"])

def render_numeric(node):
    st.write(node.get("prompt",""))
    key = f"num_{st.session_state.node_id}"
    st.number_input("Your answer", key=key, step=0.01, format="%.2f")

    if st.button("Check"):
        val = st.session_state.get(key)
        expected = node.get("expected")
        tol = node.get("tolerance", 0.0)
        if expected is None or val is None:
            st.warning("No expected value configured.")
        else:
            if abs(val - expected) <= tol:
                st.success("Looks correct (within tolerance).")
                st.session_state.score += 1
            else:
                st.info("Not quite. See guidance below.")
        if node.get("guidance"):
            st.markdown("**Guidance:**")
            st.write(node["guidance"])
        if node.get("next"):
            if st.button("Continue"):
                goto(node["next"])

def render_debrief(node):
    st.markdown("## Debrief")
    st.write("Score:", st.session_state.score)
    st.write("Completed nodes:", len(st.session_state.history))
    if st.button("Restart"):
        st.session_state.clear()
        st.rerun()

def main():
    st.set_page_config(page_title="Avian Influenza — Part A", layout="wide")
    flow = load_flow()
    init_state(flow)

    st.title(flow.get("title","Case Study"))
    node_id = st.session_state.node_id
    node = flow["nodes"].get(node_id)
    if not node:
        st.error(f"Unknown node: {node_id}")
        return

    st.sidebar.header("Progress")
    st.sidebar.write("Current:", node_id)
    st.sidebar.write("Score:", st.session_state.score)

    st.subheader(node.get("title",""))

    t = node.get("type")
    if t == "read":
        render_read(node)
    elif t == "short_answer":
        render_short_answer(node)
    elif t == "table":
        render_table(node)
    elif t == "numeric":
        render_numeric(node)
    elif t == "debrief":
        render_debrief(node)
    else:
        st.error(f"Unsupported node type: {t}")

if __name__ == "__main__":
    main()
