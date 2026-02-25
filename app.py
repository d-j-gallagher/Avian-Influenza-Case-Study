import json
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).parent
MANIFEST_REL = "content/manifest.json"

QUESTION_TYPES = {
    "question_section",
    "question",
    "short_answer",
    "free_response",
    "text_input",
    "open_ended",
    "mcq",
    "multiple_choice",
    "numeric",
}

READ_TYPES = {"read_section", "read", "table"}
SPECIAL_TYPES = {"review_answers", "debrief"}


# ----------------------------
# Cached loaders
# ----------------------------
@st.cache_data(show_spinner=False)
def load_json(rel_path: str) -> dict:
    p = BASE_DIR / rel_path
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def read_text(rel_path: str) -> str:
    p = BASE_DIR / rel_path
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


@st.cache_data(show_spinner=False)
def load_csv(rel_path: str):
    p = BASE_DIR / rel_path
    if not p.exists():
        return None
    try:
        import pandas as pd
        return pd.read_csv(p)
    except Exception:
        return None


def clear_caches():
    st.cache_data.clear()
    st.toast("Content cache cleared.", icon="✅")


# ----------------------------
# Markdown helpers (NO regex anchors)
# ----------------------------
def _is_heading_line(line: str) -> tuple[int, str] | None:
    """
    Return (level, heading_text) if line is a markdown heading (#/##/###) at start of line.
    Works even if file has weird newline semantics, because we're line-based.
    """
    if not line:
        return None
    if not line.startswith("#"):
        return None

    # Count heading level
    i = 0
    while i < len(line) and line[i] == "#":
        i += 1
    level = i

    if level < 1 or level > 3:
        return None

    # Require a space after hashes
    if i >= len(line) or line[i] != " ":
        return None

    text = line[i + 1 :].strip()
    if not text:
        return None

    return level, text


def list_headings(md_text: str):
    if not md_text:
        return []
    headings = []
    for line in md_text.splitlines():
        h = _is_heading_line(line)
        if h:
            headings.append(h[1])
    return headings


def extract_md_section(md_text: str, heading: str) -> tuple[str, bool]:
    """
    Extract content under a markdown heading matching `heading` (case-insensitive).
    Stops at the next heading of same or higher level.
    """
    if not md_text:
        return ("", False)

    lines = md_text.splitlines()
    target = heading.strip().lower()

    # Find the heading line
    start_idx = None
    start_level = None
    for idx, line in enumerate(lines):
        h = _is_heading_line(line)
        if h:
            lvl, txt = h
            if txt.strip().lower() == target:
                start_idx = idx
                start_level = lvl
                break

    if start_idx is None:
        return ("", False)

    # Collect until next heading of same-or-higher level
    out = []
    for line in lines[start_idx + 1 :]:
        h = _is_heading_line(line)
        if h:
            lvl, _ = h
            if lvl <= start_level:
                break
        out.append(line)

    return ("\n".join(out).strip(), True)


def get_node_markdown(node: dict, md_text: str) -> tuple[str, bool]:
    if not md_text.strip():
        return ("", False)

    section = node.get("section")
    if section:
        content, found = extract_md_section(md_text, section)
        if found and content.strip():
            return (content, True)
        return (md_text.strip(), False)

    return (md_text.strip(), True)


# ----------------------------
# Session state helpers
# ----------------------------
def ss_key(*parts) -> str:
    return "::".join(parts)


def init_global_state(manifest: dict):
    if "selected_part_id" not in st.session_state:
        st.session_state.selected_part_id = manifest["parts"][0]["id"]

    if "nav_mode" not in st.session_state:
        st.session_state.nav_mode = "guided"

    if "answers" not in st.session_state:
        st.session_state.answers = {}

    if "flow_state" not in st.session_state:
        st.session_state.flow_state = {}


def get_part(manifest: dict, part_id: str) -> dict:
    for p in manifest["parts"]:
        if p["id"] == part_id:
            return p
    return manifest["parts"][0]


def load_flow_for_part(part: dict) -> dict:
    return load_json(part["flow"])


def ensure_part_state(part_id: str, flow: dict):
    if part_id not in st.session_state.flow_state:
        st.session_state.flow_state[part_id] = {"node_id": flow["start"], "history": []}
    if part_id not in st.session_state.answers:
        st.session_state.answers[part_id] = {}


def current_node_id(part_id: str) -> str:
    return st.session_state.flow_state[part_id]["node_id"]


def goto(part_id: str, next_id: str):
    st.session_state.flow_state[part_id]["history"].append(current_node_id(part_id))
    st.session_state.flow_state[part_id]["node_id"] = next_id
    st.rerun()


def go_back(part_id: str):
    hist = st.session_state.flow_state[part_id]["history"]
    if hist:
        st.session_state.flow_state[part_id]["node_id"] = hist.pop()
        st.rerun()


def set_submitted(part_id: str, node_id: str, submitted: bool):
    entry = st.session_state.answers[part_id].get(node_id, {"text": "", "submitted": False})
    entry["submitted"] = submitted
    st.session_state.answers[part_id][node_id] = entry


def set_answer_text(part_id: str, node_id: str, text: str):
    entry = st.session_state.answers[part_id].get(node_id, {"text": "", "submitted": False})
    entry["text"] = text
    st.session_state.answers[part_id][node_id] = entry


# ----------------------------
# Health check
# ----------------------------
def run_health_check(flow: dict):
    issues = []
    nodes = flow.get("nodes", {})

    for nid, node in nodes.items():
        ntype = node.get("type", "")

        if ntype not in READ_TYPES and ntype not in QUESTION_TYPES and ntype not in SPECIAL_TYPES:
            issues.append(f"Node '{nid}': unknown type '{ntype}'.")

        # READ nodes require md
        if ntype in READ_TYPES:
            md = node.get("md")
            if not md:
                issues.append(f"Node '{nid}': read/table node missing 'md'.")
            else:
                p = BASE_DIR / md
                if not p.exists():
                    issues.append(f"Node '{nid}': md file not found → {md}")
                else:
                    sec = node.get("section")
                    if sec:
                        txt = read_text(md)
                        _, found = extract_md_section(txt, sec)
                        if not found:
                            heads = list_headings(txt)
                            issues.append(
                                f"Node '{nid}': section '{sec}' not found in {md}. "
                                f"Headings seen: {', '.join(heads[:10]) if heads else '(none)'}"
                            )

        # QUESTION nodes require prompt or md
        if ntype in QUESTION_TYPES:
            if not node.get("prompt") and not node.get("md"):
                issues.append(f"Node '{nid}': question node missing both 'prompt' and 'md'.")
            md = node.get("md")
            if md:
                p = BASE_DIR / md
                if not p.exists():
                    issues.append(f"Node '{nid}': md file not found → {md}")
                else:
                    sec = node.get("section")
                    if sec:
                        txt = read_text(md)
                        _, found = extract_md_section(txt, sec)
                        if not found:
                            heads = list_headings(txt)
                            issues.append(
                                f"Node '{nid}': section '{sec}' not found in {md}. "
                                f"Headings seen: {', '.join(heads[:10]) if heads else '(none)'}"
                            )

        nxt = node.get("next")
        if nxt and nxt not in nodes:
            issues.append(f"Node '{nid}': next points to missing node '{nxt}'.")

    start = flow.get("start")
    if start and start not in nodes:
        issues.append(f"Flow start '{start}' not found in nodes.")

    return issues


# ----------------------------
# Sidebar
# ----------------------------
def sidebar(manifest: dict, part: dict, flow: dict):
    st.sidebar.header("Navigation")
    st.session_state.nav_mode = st.sidebar.radio(
        "Mode",
        ["guided", "jump"],
        format_func=lambda v: "Guided (Next/Back)" if v == "guided" else "Jump to Section",
        index=0 if st.session_state.nav_mode == "guided" else 1
    )

    st.sidebar.divider()
    st.sidebar.header("Parts")
    for p in manifest["parts"]:
        label = p["title"]
        if p["id"] == part["id"]:
            label = f"📘 {label}"
        if st.sidebar.button(label, key=ss_key("partbtn", p["id"])):
            st.session_state.selected_part_id = p["id"]
            st.rerun()

    st.sidebar.divider()
    with st.sidebar.expander("Content health check", expanded=False):
        issues = run_health_check(flow)
        if not issues:
            st.success("No issues found.")
        else:
            st.warning(f"{len(issues)} issue(s) found:")
            for it in issues:
                st.write("- " + it)

    if st.sidebar.button("Reload content (clear cache)"):
        clear_caches()
        st.rerun()


# ----------------------------
# Progress
# ----------------------------
def progress_summary(part_id: str, flow: dict) -> tuple[int, int]:
    q_nodes = [nid for nid, n in flow["nodes"].items() if n.get("type") in QUESTION_TYPES]
    submitted = sum(
        1 for nid in q_nodes
        if st.session_state.answers.get(part_id, {}).get(nid, {}).get("submitted", False)
    )
    return submitted, len(q_nodes)


def get_answer_key(node: dict):
    if node.get("answer_key"):
        return node["answer_key"]
    if node.get("answer_guidance"):
        return node["answer_guidance"]
    if node.get("guidance"):
        return node["guidance"]
    return None


# ----------------------------
# Render node
# ----------------------------
def render_node(part_id: str, flow: dict, node_id: str):
    node = flow["nodes"][node_id]
    ntype = node.get("type", "")

    st.subheader(node.get("title", node_id))

    md_text = read_text(node["md"]) if node.get("md") else ""

    if ntype in READ_TYPES:
        if node.get("md"):
            content, ok = get_node_markdown(node, md_text)
            if node.get("section") and not ok:
                st.warning("This step asked for a section heading that wasn’t found. Showing full page instead.")
            st.markdown(content if content.strip() else "_(No content)_")
        else:
            st.warning("Read/table node has no markdown file to display.")

        if ntype == "table":
            csv_path = node.get("csv")
            if csv_path:
                df = load_csv(csv_path)
                if df is None:
                    st.warning(f"Could not load table CSV: {csv_path}")
                else:
                    st.dataframe(df, use_container_width=True)

        cols = st.columns([1, 1])
        cols[0].button("⬅ Back", on_click=go_back, args=(part_id,), disabled=not bool(st.session_state.flow_state[part_id]["history"]))
        if node.get("next"):
            cols[1].button("Next ➜", on_click=goto, args=(part_id, node["next"]))
        return

    if ntype == "numeric":
        if node.get("prompt"):
            st.markdown(node["prompt"])

        existing = st.session_state.answers[part_id].get(node_id, {"text": "", "submitted": False})
        try:
            default_val = float(existing.get("text")) if existing.get("text") else 0.0
        except Exception:
            default_val = 0.0

        value = st.number_input("Your response (number)", value=default_val)
        set_answer_text(part_id, node_id, str(value))

        cols = st.columns([1, 1, 1])
        cols[0].button("⬅ Back", on_click=go_back, args=(part_id,), disabled=not bool(st.session_state.flow_state[part_id]["history"]))

        if cols[1].button("Submit"):
            set_submitted(part_id, node_id, True)
            st.success("Submitted.")

        if node.get("next"):
            cols[2].button("Continue ➜", on_click=goto, args=(part_id, node["next"]))

        if st.session_state.answers[part_id].get(node_id, {}).get("submitted", False):
            expected = node.get("expected")
            tol = node.get("tolerance", 0)
            unit = node.get("unit", "")
            if expected is not None:
                try:
                    ok = abs(float(value) - float(expected)) <= float(tol)
                    st.success(f"Within tolerance (expected ≈ {expected}{unit}).") if ok else st.warning(f"Not within tolerance (expected ≈ {expected}{unit}).")
                except Exception:
                    pass

            key = get_answer_key(node)
            if key:
                with st.expander("Check the answer (unlocked after submit)", expanded=False):
                    st.write(key)
        return

    if ntype in QUESTION_TYPES:
        if node.get("prompt"):
            st.markdown(node["prompt"])

        # optional md
        if node.get("md"):
            content, ok = get_node_markdown(node, md_text)
            if node.get("section") and not ok:
                st.warning("This step asked for a section heading that wasn’t found. Showing full page instead.")
            if content.strip():
                st.markdown(content)

        existing = st.session_state.answers[part_id].get(node_id, {"text": "", "submitted": False})
        text = st.text_area("Your response", value=existing.get("text", ""), height=180)
        set_answer_text(part_id, node_id, text)

        cols = st.columns([1, 1, 1])
        cols[0].button("⬅ Back", on_click=go_back, args=(part_id,), disabled=not bool(st.session_state.flow_state[part_id]["history"]))

        if cols[1].button("Submit"):
            if text.strip():
                set_submitted(part_id, node_id, True)
                st.success("Submitted.")
            else:
                st.warning("Type a response before submitting.")

        if node.get("next"):
            cols[2].button("Continue ➜", on_click=goto, args=(part_id, node["next"]))

        if st.session_state.answers[part_id].get(node_id, {}).get("submitted", False):
            key = get_answer_key(node)
            if key:
                with st.expander("Check the answer (unlocked after submit)", expanded=False):
                    if isinstance(key, list):
                        for line in key:
                            st.write(f"- {line}")
                    else:
                        st.write(key)

            agmd = node.get("answer_guidance_md")
            if agmd:
                ref = read_text(agmd)
                if ref.strip():
                    with st.expander("Reference material (unlocked after submit)", expanded=False):
                        st.markdown(ref)
        return

    if ntype == "debrief":
        st.write("Completed this part.")
        st.json(st.session_state.answers.get(part_id, {}))
        cols = st.columns([1, 1, 1])
        cols[0].button("⬅ Back", on_click=go_back, args=(part_id,), disabled=not bool(st.session_state.flow_state[part_id]["history"]))
        if cols[1].button("Restart part"):
            st.session_state.flow_state[part_id] = {"node_id": flow["start"], "history": []}
            st.rerun()
        if cols[2].button("Clear my answers for this part"):
            st.session_state.answers[part_id] = {}
            st.rerun()
        return

    st.error(f"Unsupported node type: {ntype}")


# ----------------------------
# Tabs
# ----------------------------
def learn_and_respond_tab(part_id: str, flow: dict):
    submitted, total = progress_summary(part_id, flow)
    st.caption(f"Progress: {submitted}/{total} questions submitted")
    render_node(part_id, flow, current_node_id(part_id))


def review_answers_tab(part_id: str, flow: dict):
    st.header("Review Answers")
    q_nodes = [(nid, n) for nid, n in flow["nodes"].items() if n.get("type") in QUESTION_TYPES]
    if not q_nodes:
        st.info("No questions detected in this part yet.")
        return

    for nid, n in q_nodes:
        title = n.get("title", nid)
        entry = st.session_state.answers.get(part_id, {}).get(nid, {"text": "", "submitted": False})
        status = "✅ submitted" if entry.get("submitted") else "⏳ pending"
        preview = (entry.get("text") or "").strip() or "No response yet"

        with st.container(border=True):
            cols = st.columns([2, 4, 1])
            cols[0].write(f"**{title}**")
            cols[1].write(preview[:180] + ("…" if len(preview) > 180 else ""))
            if cols[2].button("Go", key=ss_key("go", part_id, nid)):
                st.session_state.flow_state[part_id]["node_id"] = nid
                st.rerun()
            st.caption(status)


def appendices_tab(manifest: dict):
    st.header("Appendices")
    if not manifest.get("appendices"):
        st.info("No appendices added yet.")
        return
    for app in manifest["appendices"]:
        st.write(app)


# ----------------------------
# Main
# ----------------------------
def main():
    manifest = load_json(MANIFEST_REL)
    init_global_state(manifest)

    st.set_page_config(page_title=manifest.get("title", "Case Study"), layout="wide")

    part = get_part(manifest, st.session_state.selected_part_id)
    flow = load_flow_for_part(part)
    ensure_part_state(part["id"], flow)

    sidebar(manifest, part, flow)

    st.title(manifest.get("title", "Case Study"))
    st.markdown(f"## {flow.get('title', part['title'])}")

    tab1, tab2, tab3 = st.tabs(["Learn & Respond", "Review Answers", "Appendices"])
    with tab1:
        learn_and_respond_tab(part["id"], flow)
    with tab2:
        review_answers_tab(part["id"], flow)
    with tab3:
        appendices_tab(manifest)


if __name__ == "__main__":
    main()