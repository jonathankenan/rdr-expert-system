import pytest

from rdr import Condition, KnowledgeBase, RDRError
from rdr.schema import ATTRIBUTES, DEFAULT_CONCLUSION

BASE = {
    "usia": 25, "bmi": 22.0, "tujuan": "kebugaran_umum", "level": "pemula",
    "hari_luang": 3, "durasi_sesi": 45, "cedera": "tidak_ada", "fasilitas": "gym",
}


def case(**kw):
    return {**BASE, **kw}


@pytest.fixture
def kb():
    return KnowledgeBase(DEFAULT_CONCLUSION)


def test_initial_kb_returns_default(kb):
    r = kb.infer(BASE)
    assert r.conclusion == DEFAULT_CONCLUSION
    assert r.fired_node_id == 0
    assert (r.attach_parent_id, r.attach_side) == (0, "true")


def test_exception_on_root(kb):
    c1 = case(bmi=32.0, tujuan="turun_berat")
    rule = kb.add_rule(c1, "Kardio low-impact 5x seminggu", [Condition("bmi", ">=", 30.0)])
    assert kb.root.true_child == rule.id
    assert rule.cornerstone == c1
    assert kb.infer(c1).conclusion == "Kardio low-impact 5x seminggu"
    assert kb.infer(BASE).conclusion == DEFAULT_CONCLUSION


def test_nested_exception_uses_cornerstone_difference(kb):
    c1 = case(bmi=32.0, tujuan="turun_berat")
    r1 = kb.add_rule(c1, "Kardio low-impact", [Condition("bmi", ">=", 30.0)])

    c2 = case(bmi=35.0, tujuan="turun_berat", cedera="lutut", fasilitas="kolam_renang")
    res = kb.infer(c2)
    assert res.fired_node_id == r1.id
    assert (res.attach_parent_id, res.attach_side) == (r1.id, "true")

    diffs = {str(d) for d in kb.difference_list(c2, kb.cornerstone_for(res), ATTRIBUTES)}
    assert diffs == {
        "bmi > 32", "cedera == lutut", "cedera != tidak_ada",
        "fasilitas == kolam_renang", "fasilitas != gym",
    }

    # kondisi yang juga dipenuhi kasus kunci ditolak
    with pytest.raises(RDRError):
        kb.add_rule(c2, "Renang", [Condition("tujuan", "==", "turun_berat")])

    r2 = kb.add_rule(c2, "Renang / aqua jogging", [Condition("cedera", "==", "lutut")])
    assert kb.nodes[r1.id].true_child == r2.id
    assert kb.infer(c2).conclusion == "Renang / aqua jogging"
    # kasus kunci rule lama tetap menghasilkan kesimpulan lama
    assert kb.infer(c1).conclusion == "Kardio low-impact"


def test_false_child_attachment(kb):
    c1 = case(bmi=32.0)
    r1 = kb.add_rule(c1, "Kardio low-impact", [Condition("bmi", ">=", 30.0)])

    c3 = case(usia=65)
    res = kb.infer(c3)
    assert res.fired_node_id == 0
    assert (res.attach_parent_id, res.attach_side) == (r1.id, "false")

    r3 = kb.add_rule(c3, "Jalan cepat + latihan keseimbangan", [Condition("usia", ">=", 60)])
    assert kb.nodes[r1.id].false_child == r3.id
    assert kb.infer(c3).conclusion == "Jalan cepat + latihan keseimbangan"
    path = [(s.node_id, s.satisfied) for s in kb.infer(c3).path]
    assert path == [(0, True), (r1.id, False), (r3.id, True)]


def test_last_fired_wins_through_false_branch(kb):
    # rule pada false-child dari sebuah perkecualian tetap mengalahkan rule leluhurnya
    c1 = case(bmi=32.0)
    r1 = kb.add_rule(c1, "A", [Condition("bmi", ">=", 30.0)])
    c2 = case(bmi=31.0, cedera="bahu")
    r2 = kb.add_rule(c2, "B", [Condition("cedera", "==", "bahu")])
    c3 = case(bmi=31.0, cedera="punggung")
    res = kb.infer(c3)
    assert res.conclusion == "A"
    assert (res.attach_parent_id, res.attach_side) == (r2.id, "false")
    r3 = kb.add_rule(c3, "C", [Condition("cedera", "==", "punggung")])
    assert kb.nodes[r2.id].false_child == r3.id
    assert kb.infer(c3).conclusion == "C"
    assert kb.infer(c2).conclusion == "B"
    assert kb.infer(c1).conclusion == "A"


def test_numeric_threshold_must_separate_cases(kb):
    c1 = case(bmi=32.0)
    kb.add_rule(c1, "A", [Condition("bmi", ">=", 30.0)])
    c2 = case(bmi=36.0)
    with pytest.raises(RDRError):          # 32 juga > 31
        kb.add_rule(c2, "B", [Condition("bmi", ">", 31.0)])
    with pytest.raises(RDRError):          # 36 tidak > 36
        kb.add_rule(c2, "B", [Condition("bmi", ">", 36.0)])
    kb.add_rule(c2, "B", [Condition("bmi", ">", 34.0)])
    assert kb.infer(c2).conclusion == "B"


def test_rejects_empty_or_same_conclusion(kb):
    with pytest.raises(RDRError):
        kb.add_rule(BASE, "X", [])
    with pytest.raises(RDRError):
        kb.add_rule(BASE, DEFAULT_CONCLUSION, [Condition("usia", ">=", 25)])


def test_identical_case_has_no_difference(kb):
    kb.add_rule(case(bmi=32.0), "A", [Condition("bmi", ">=", 30.0)])
    res = kb.infer(case(bmi=32.0))
    assert kb.difference_list(case(bmi=32.0), kb.cornerstone_for(res), ATTRIBUTES) == []


def test_save_load_roundtrip(kb, tmp_path):
    kb.add_rule(case(bmi=32.0), "A", [Condition("bmi", ">=", 30.0)])
    kb.add_rule(case(usia=70), "B", [Condition("usia", ">=", 60)])
    kb.log(BASE, DEFAULT_CONCLUSION, DEFAULT_CONCLUSION, True)
    p = tmp_path / "kb.json"
    kb.save(p)
    kb2 = KnowledgeBase.load(p)
    assert kb2.to_dict() == kb.to_dict()
    assert kb2.infer(case(usia=70)).conclusion == "B"
    r = kb2.add_rule(case(usia=70, cedera="lutut"), "C", [Condition("cedera", "==", "lutut")])
    assert r.id == 3


def test_rule_text_format(kb):
    r = kb.add_rule(case(bmi=32.0), "A", [Condition("bmi", ">=", 30.0)])
    assert kb.root.to_text() == f"IF true THEN {DEFAULT_CONCLUSION}"
    assert r.to_text().startswith("IF bmi >= 30 THEN A BECAUSE OF [usia=25, bmi=32,")
