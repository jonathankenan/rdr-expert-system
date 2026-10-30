"""UI Streamlit untuk sistem pakar RDR. Jalankan: streamlit run app.py"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st

from rdr import Condition, KnowledgeBase, RDRError
from rdr.engine import fmt_value
from rdr.schema import ATTR_BY_NAME, ATTRIBUTES, DEFAULT_CONCLUSION, DOMAIN_NAME, EXPERT_ROLE

ROOT = Path(__file__).parent
KB_PATH = ROOT / "kb.json"
DEMO_KB_PATH = ROOT / "examples" / "kb_demo.json"
NEW_CONCLUSION = "➕ Tulis kesimpulan baru…"

st.set_page_config(page_title=f"RDR – {DOMAIN_NAME}", page_icon="🏋️", layout="wide")


# ---------------- state ----------------
def load_kb() -> KnowledgeBase:
    if KB_PATH.exists():
        try:
            return KnowledgeBase.load(KB_PATH)
        except (RDRError, KeyError, json.JSONDecodeError):
            st.warning("kb.json rusak, memulai KB baru.")
    return KnowledgeBase(DEFAULT_CONCLUSION)


def save_kb() -> None:
    st.session_state.kb.save(KB_PATH)


def reset_consultation() -> None:
    st.session_state.case = None
    st.session_state.result = None
    st.session_state.phase = None
    st.session_state.system_conclusion = None
    st.session_state.acq_id = st.session_state.get("acq_id", 0) + 1


if "kb" not in st.session_state:
    st.session_state.kb = load_kb()
    reset_consultation()

kb: KnowledgeBase = st.session_state.kb


def pretty(v) -> str:
    return fmt_value(v).replace("_", " ") if isinstance(v, str) else fmt_value(v)


def attr_label(name: str) -> str:
    a = ATTR_BY_NAME.get(name)
    if not a:
        return name
    return f"{a['label']} ({a['unit']})" if a.get("unit") else a["label"]


# ---------------- pohon (graphviz) ----------------
def wrap(text: str, width: int = 34) -> str:
    lines = []
    for part in text.split("\n"):
        lines.extend(textwrap.wrap(part, width) or [""])
    return "\\n".join(l.replace("\\", "\\\\").replace('"', '\\"') for l in lines)


def tree_dot(result=None, pending: tuple[int, str] | None = None) -> str:
    evaluated = {s.node_id: s.satisfied for s in result.path} if result else {}
    fired = result.fired_node_id if result else None
    out = [
        "digraph RDR {",
        'graph [rankdir=TB, nodesep=0.35, ranksep=0.5, ordering=out, bgcolor="transparent"];',
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#ffffff", color="#888888"];',
        'edge [fontname="Helvetica", fontsize=9];',
    ]
    for n in kb.nodes.values():
        label = wrap(f"Rule #{n.id}\nIF {n.condition_text()}\nTHEN {n.conclusion}")
        attrs = [f'label="{label}"']
        if n.id == fired:
            attrs += ['fillcolor="#2e7d32"', 'fontcolor="white"', 'penwidth=2.5', 'color="#1b5e20"']
        elif evaluated.get(n.id) is True:
            attrs += ['fillcolor="#c8e6c9"', 'color="#2e7d32"']
        elif evaluated.get(n.id) is False:
            attrs += ['fillcolor="#ffcdd2"', 'color="#c62828"']
        out.append(f'n{n.id} [{", ".join(attrs)}];')

    for n in kb.nodes.values():
        slots = {"false": n.false_child, "true": n.true_child}
        if pending and pending[0] == n.id:
            slots[pending[1]] = "new"
        if slots["false"] is None and slots["true"] is None:
            continue
        # anak kiri = false-child, anak kanan = true-child; slot kosong diberi node tak terlihat
        for side in ("false", "true"):
            child = slots[side]
            color = "#2e7d32" if side == "true" else "#c62828"
            elabel = "true (except)" if side == "true" else "false (else)"
            if child is None:
                out.append(f'x{n.id}{side} [style=invis, label=""];')
                out.append(f"n{n.id} -> x{n.id}{side} [style=invis];")
            elif child == "new":
                out.append(f'new [label="Rule baru\\n(akan dipasang di sini)", style="dashed,rounded", color="{color}", fontcolor="{color}"];')
                out.append(f'n{n.id} -> new [label="{elabel}", color="{color}", fontcolor="{color}", style=dashed];')
            else:
                on_path = child in evaluated and n.id in evaluated
                width = 2.5 if on_path else 1
                out.append(f'n{n.id} -> n{child} [label="{elabel}", color="{color}", fontcolor="{color}", penwidth={width}];')
    out.append("}")
    return "\n".join(out)


# ---------------- sidebar ----------------
with st.sidebar:
    st.header("🏋️ " + DOMAIN_NAME)
    st.caption(f"Sistem pakar berbasis Ripple Down Rules. Pakar: **{EXPERT_ROLE}**.")
    c1, c2 = st.columns(2)
    c1.metric("Jumlah rule", len(kb.nodes))
    c2.metric("Kasus ditangani", len(kb.history))

    st.divider()
    st.subheader("Basis pengetahuan")
    st.download_button(
        "⬇️ Unduh KB (JSON)",
        json.dumps(kb.to_dict(), indent=2, ensure_ascii=False),
        file_name="kb.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("Muat KB dari file JSON", type="json")
    if uploaded is not None and st.session_state.get("uploaded_id") != uploaded.file_id:
        try:
            st.session_state.kb = KnowledgeBase.from_dict(json.load(uploaded))
            st.session_state.uploaded_id = uploaded.file_id
            save_kb()
            reset_consultation()
            st.rerun()
        except (RDRError, KeyError, json.JSONDecodeError) as e:
            st.error(f"Gagal memuat KB: {e}")

    if DEMO_KB_PATH.exists() and st.button("📦 Muat KB contoh", use_container_width=True):
        st.session_state.kb = KnowledgeBase.load(DEMO_KB_PATH)
        save_kb()
        reset_consultation()
        st.rerun()

    with st.expander("♻️ Reset KB ke Rule 0"):
        default = st.text_area("Kesimpulan default (Rule 0)", DEFAULT_CONCLUSION)
        if st.button("Reset sekarang", type="primary", use_container_width=True):
            st.session_state.kb = KnowledgeBase(default.strip() or DEFAULT_CONCLUSION)
            save_kb()
            reset_consultation()
            st.rerun()


# ---------------- tabs ----------------
tab_consult, tab_tree, tab_rules, tab_history = st.tabs(
    ["🧑‍🏫 Konsultasi", "🌳 Pohon RDR", "📜 Daftar Rule", "🗂️ Riwayat Kasus"]
)


def render_path(result) -> None:
    for step in result.path:
        n = kb.nodes[step.node_id]
        if step.satisfied:
            nxt = "lanjut ke true-child (perkecualian)" if n.true_child is not None else "tidak ada true-child, berhenti"
            st.markdown(f"✅ **Rule #{n.id}** `IF {n.condition_text()}` terpenuhi → kesimpulan sementara: *{n.conclusion}* · {nxt}")
        else:
            nxt = "lanjut ke false-child" if n.false_child is not None else "tidak ada false-child, berhenti"
            st.markdown(f"❌ **Rule #{n.id}** `IF {n.condition_text()}` tidak terpenuhi · {nxt}")


def render_acquisition(case: dict, result) -> None:
    acq = st.session_state.acq_id
    fired = kb.nodes[result.fired_node_id]
    cornerstone = fired.cornerstone
    side_txt = "true-child (perkecualian)" if result.attach_side == "true" else "false-child"

    st.subheader("✍️ Akuisisi pengetahuan")
    st.markdown(
        f"Kesimpulan berasal dari **Rule #{fired.id}**. Rule baru akan menjadi perkecualian baginya, "
        f"dipasang sebagai **{side_txt}** dari **Rule #{result.attach_parent_id}**."
    )

    # 1. kesimpulan yang benar
    options = [c for c in kb.conclusions() if c != result.conclusion] + [NEW_CONCLUSION]
    choice = st.selectbox("1. Kesimpulan yang benar menurut pakar", options, index=len(options) - 1, key=f"concl_sel_{acq}")
    conclusion = st.text_area("Kesimpulan baru", key=f"concl_new_{acq}") if choice == NEW_CONCLUSION else choice

    # 2. perbandingan dengan kasus kunci
    st.markdown("**2. Perbandingan kasus baru dengan kasus kunci**")
    if cornerstone is None:
        st.info("Rule #0 tidak punya kasus kunci, jadi kondisi apa pun yang dipenuhi kasus baru boleh dipilih.")
    else:
        rows = [
            {
                "Atribut": attr_label(a["name"]),
                "Kasus baru": pretty(case.get(a["name"])),
                f"Kasus kunci Rule #{fired.id}": pretty(cornerstone.get(a["name"])),
                "Berbeda": "⚠️" if case.get(a["name"]) != cornerstone.get(a["name"]) else "",
            }
            for a in ATTRIBUTES
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # 3. pilih kondisi dari daftar perbedaan
    candidates = kb.difference_list(case, cornerstone, ATTRIBUTES)
    st.markdown("**3. Pilih kondisi rule baru** (dipenuhi kasus baru, tidak dipenuhi kasus kunci)")
    if not candidates:
        st.error(
            "Kasus baru identik dengan kasus kunci pada semua atribut, sehingga tidak ada kondisi yang dapat "
            "membedakannya. Periksa kembali data kasus atau tambahkan atribut baru ke domain."
        )
        if st.button("Batal", key=f"cancel_{acq}"):
            st.session_state.phase = "result"
            st.rerun()
        return

    chosen: list[Condition] = []
    for i, cand in enumerate(candidates):
        meta = ATTR_BY_NAME[cand.attr]
        cols = st.columns([3, 2])
        checked = cols[0].checkbox(f"`{cand}`", key=f"cand_{acq}_{i}")
        value = cand.value
        if meta["type"] == "numeric":
            is_int = isinstance(meta["step"], int)
            value = cols[1].number_input(
                f"Ambang {cand.attr} {cand.op}",
                value=int(cand.value) if is_int else float(cand.value),
                step=meta["step"],
                format="%d" if is_int else "%.1f",
                key=f"thr_{acq}_{i}",
                label_visibility="collapsed",
                disabled=not checked,
            )
        if checked:
            chosen.append(Condition(cand.attr, cand.op, value))

    if chosen:
        preview = " AND ".join(str(c) for c in chosen)
        st.code(f"IF {preview} THEN {conclusion or '…'}", language=None)

    b1, b2 = st.columns(2)
    if b1.button("💾 Simpan rule baru", type="primary", use_container_width=True, key=f"save_{acq}"):
        try:
            node = kb.add_rule(case, conclusion or "", chosen)
        except RDRError as e:
            st.error(str(e))
        else:
            new_result = kb.infer(case)
            kb.log(case, st.session_state.system_conclusion, new_result.conclusion, False, node.id)
            save_kb()
            st.session_state.result = new_result
            st.session_state.phase = "done"
            st.session_state.flash = f"Rule #{node.id} ditambahkan ke basis pengetahuan."
            st.rerun()
    if b2.button("Batal", use_container_width=True, key=f"cancel_{acq}"):
        st.session_state.phase = "result"
        st.rerun()


with tab_consult:
    col_form, col_out = st.columns([1, 2], gap="large")

    with col_form:
        st.subheader("Data konsumen")
        with st.form("case_form"):
            new_case = {}
            for a in ATTRIBUTES:
                if a["type"] == "numeric":
                    new_case[a["name"]] = st.number_input(
                        attr_label(a["name"]), min_value=a["min"], max_value=a["max"],
                        value=a["default"], step=a["step"],
                        format="%.1f" if isinstance(a["step"], float) else "%d",
                    )
                else:
                    new_case[a["name"]] = st.selectbox(
                        a["label"], a["options"], format_func=lambda v: v.replace("_", " ")
                    )
            if st.form_submit_button("🔎 Cari rekomendasi", type="primary", use_container_width=True):
                if isinstance(new_case["bmi"], float):
                    new_case["bmi"] = round(new_case["bmi"], 1)
                reset_consultation()
                st.session_state.case = new_case
                st.session_state.result = kb.infer(new_case)
                st.session_state.system_conclusion = st.session_state.result.conclusion
                st.session_state.phase = "result"
        with st.expander("Kalkulator BMI"):
            berat = st.number_input("Berat (kg)", 20.0, 250.0, 65.0, 0.5)
            tinggi = st.number_input("Tinggi (cm)", 100.0, 230.0, 170.0, 0.5)
            st.write(f"BMI = **{berat / (tinggi / 100) ** 2:.1f}**")

    with col_out:
        phase = st.session_state.phase
        case, result = st.session_state.case, st.session_state.result
        if flash := st.session_state.pop("flash", None):
            st.toast(flash, icon="✅")

        if phase is None:
            st.info("Isi data konsumen lalu tekan **Cari rekomendasi**.")
        else:
            box = st.success if phase == "done" else st.info
            title = "Rekomendasi final" if phase == "done" else "Rekomendasi sistem"
            box(f"**{title}:** {result.conclusion}\n\n_(dari Rule #{result.fired_node_id})_")

            with st.expander("Jalur inferensi", expanded=phase != "done"):
                render_path(result)

            if phase == "result":
                st.markdown(f"**Apakah {EXPERT_ROLE.lower()} setuju dengan rekomendasi ini?**")
                b1, b2 = st.columns(2)
                if b1.button("👍 Setuju", type="primary", use_container_width=True):
                    kb.log(case, result.conclusion, result.conclusion, True)
                    save_kb()
                    st.session_state.phase = "done"
                    st.session_state.flash = "Rekomendasi disetujui pakar."
                    st.rerun()
                if b2.button("👎 Tidak setuju", use_container_width=True):
                    st.session_state.phase = "acquire"
                    st.rerun()
            elif phase == "acquire":
                render_acquisition(case, result)
                st.markdown("**Posisi rule baru pada pohon:**")
                st.graphviz_chart(tree_dot(result, (result.attach_parent_id, result.attach_side)))
            elif phase == "done":
                if st.button("🔄 Konsultasi baru"):
                    reset_consultation()
                    st.rerun()


with tab_tree:
    st.caption(
        "Anak **kanan (hijau)** = true-child/perkecualian, dievaluasi bila kondisi terpenuhi. "
        "Anak **kiri (merah)** = false-child, dievaluasi bila kondisi tidak terpenuhi. "
        "Jalur konsultasi terakhir disorot; node hijau tua = rule terakhir yang terpenuhi."
    )
    st.graphviz_chart(tree_dot(st.session_state.result), use_container_width=True)


with tab_rules:
    for n in sorted(kb.nodes.values(), key=lambda n: n.id):
        pos = "root" if n.parent is None else f"{kb.side_of(n.id)}-child dari Rule #{n.parent}"
        st.markdown(f"**Rule #{n.id}** · {pos}")
        st.code(n.to_text(), language=None)


with tab_history:
    if not kb.history:
        st.info("Belum ada kasus yang ditangani.")
    else:
        rows = []
        for i, h in enumerate(reversed(kb.history), 1):
            rows.append({
                "#": len(kb.history) - i + 1,
                "Waktu": h["time"],
                **{ATTR_BY_NAME[k]["label"] if k in ATTR_BY_NAME else k: pretty(v) for k, v in h["case"].items()},
                "Kesimpulan sistem": h["system_conclusion"],
                "Kesimpulan final": h["final_conclusion"],
                "Pakar setuju": "✅" if h["accepted"] else "❌",
                "Rule baru": f"#{h['new_rule_id']}" if h["new_rule_id"] is not None else "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
