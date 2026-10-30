"""Engine Single-Classification Ripple Down Rules (SCRDR).

Struktur basis pengetahuan berupa pohon biner:
  - true_child  (anak kanan): perkecualian, dievaluasi jika kondisi node terpenuhi
  - false_child (anak kiri) : alternatif, dievaluasi jika kondisi node tidak terpenuhi

Kesimpulan akhir = kesimpulan dari rule TERAKHIR yang terpenuhi pada jalur inferensi.
Rule baru selalu dipasang di posisi kosong tempat inferensi berhenti, dengan kondisi
yang dipenuhi kasus baru tetapi tidak dipenuhi kasus kunci (cornerstone case) dari
rule terakhir yang terpenuhi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

NUMERIC_OPS = (">", ">=", "<", "<=", "==", "!=")
CATEGORICAL_OPS = ("==", "!=")


def fmt_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


@dataclass(frozen=True)
class Condition:
    attr: str
    op: str
    value: Any

    def holds(self, case: dict) -> bool:
        if self.attr not in case or case[self.attr] is None:
            return False
        v = case[self.attr]
        if self.op == "==":
            return v == self.value
        if self.op == "!=":
            return v != self.value
        if self.op == ">":
            return v > self.value
        if self.op == ">=":
            return v >= self.value
        if self.op == "<":
            return v < self.value
        if self.op == "<=":
            return v <= self.value
        raise ValueError(f"Operator tidak dikenal: {self.op}")

    def __str__(self) -> str:
        return f"{self.attr} {self.op} {fmt_value(self.value)}"

    def to_dict(self) -> dict:
        return {"attr": self.attr, "op": self.op, "value": self.value}

    @staticmethod
    def from_dict(d: dict) -> "Condition":
        return Condition(d["attr"], d["op"], d["value"])


@dataclass
class Node:
    id: int
    conditions: list[Condition]
    conclusion: str
    cornerstone: dict | None = None
    true_child: int | None = None
    false_child: int | None = None
    parent: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def matches(self, case: dict) -> bool:
        # Rule 0 (kondisi kosong) selalu terpenuhi.
        return all(c.holds(case) for c in self.conditions)

    def condition_text(self) -> str:
        return " AND ".join(str(c) for c in self.conditions) if self.conditions else "true"

    def to_text(self) -> str:
        text = f"IF {self.condition_text()} THEN {self.conclusion}"
        if self.cornerstone is not None:
            kk = ", ".join(f"{k}={fmt_value(v)}" for k, v in self.cornerstone.items())
            text += f" BECAUSE OF [{kk}]"
        return text

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conditions": [c.to_dict() for c in self.conditions],
            "conclusion": self.conclusion,
            "cornerstone": self.cornerstone,
            "true_child": self.true_child,
            "false_child": self.false_child,
            "parent": self.parent,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Node":
        return Node(
            id=d["id"],
            conditions=[Condition.from_dict(c) for c in d["conditions"]],
            conclusion=d["conclusion"],
            cornerstone=d.get("cornerstone"),
            true_child=d.get("true_child"),
            false_child=d.get("false_child"),
            parent=d.get("parent"),
            created_at=d.get("created_at", ""),
        )


@dataclass
class PathStep:
    node_id: int
    satisfied: bool


@dataclass
class InferenceResult:
    conclusion: str
    fired_node_id: int          # rule terakhir yang terpenuhi
    path: list[PathStep]        # seluruh node yang dievaluasi, berurutan
    attach_parent_id: int       # node terakhir yang dievaluasi
    attach_side: str            # "true" / "false": cabang kosong tempat rule baru dipasang


class RDRError(ValueError):
    pass


class KnowledgeBase:
    def __init__(self, default_conclusion: str):
        root = Node(id=0, conditions=[], conclusion=default_conclusion)
        self.nodes: dict[int, Node] = {0: root}
        self.history: list[dict] = []
        self._next_id = 1

    @property
    def root(self) -> Node:
        return self.nodes[0]

    # ---------- inferensi ----------
    def infer(self, case: dict) -> InferenceResult:
        node = self.root
        fired = node
        path: list[PathStep] = []
        while True:
            satisfied = node.matches(case)
            path.append(PathStep(node.id, satisfied))
            if satisfied:
                fired = node
                next_id, side = node.true_child, "true"
            else:
                next_id, side = node.false_child, "false"
            if next_id is None:
                return InferenceResult(fired.conclusion, fired.id, path, node.id, side)
            node = self.nodes[next_id]

    # ---------- akuisisi pengetahuan ----------
    def difference_list(self, case: dict, cornerstone: dict | None, schema: list[dict]) -> list[Condition]:
        """Kandidat kondisi: dipenuhi kasus baru dan TIDAK dipenuhi kasus kunci.

        Untuk atribut numerik, ambang default = nilai kasus kunci (kondisi paling umum
        yang masih memisahkan kedua kasus); pakar boleh menggeser ambang selama
        pemisahan itu tetap berlaku.
        """
        candidates: list[Condition] = []
        for attr in schema:
            name = attr["name"]
            if name not in case:
                continue
            new_v = case[name]
            if cornerstone is None or name not in cornerstone:
                # Rule terakhir adalah Rule 0 (tanpa kasus kunci): semua kondisi kasus baru boleh.
                if attr["type"] == "numeric":
                    candidates.append(Condition(name, ">=", new_v))
                    candidates.append(Condition(name, "<=", new_v))
                else:
                    candidates.append(Condition(name, "==", new_v))
                continue
            kk_v = cornerstone[name]
            if new_v == kk_v:
                continue
            if attr["type"] == "numeric":
                candidates.append(Condition(name, ">" if new_v > kk_v else "<", kk_v))
            else:
                candidates.append(Condition(name, "==", new_v))
                candidates.append(Condition(name, "!=", kk_v))
        return candidates

    def cornerstone_for(self, result: InferenceResult) -> dict | None:
        return self.nodes[result.fired_node_id].cornerstone

    def validate_conditions(self, case: dict, cornerstone: dict | None, conditions: list[Condition]) -> None:
        if not conditions:
            raise RDRError("Pilih minimal satu kondisi untuk rule baru.")
        for c in conditions:
            if not c.holds(case):
                raise RDRError(f"Kondisi '{c}' tidak dipenuhi oleh kasus baru.")
            if cornerstone is not None and c.holds(cornerstone):
                raise RDRError(f"Kondisi '{c}' juga dipenuhi oleh kasus kunci, sehingga tidak membedakan keduanya.")

    def add_rule(self, case: dict, conclusion: str, conditions: list[Condition]) -> Node:
        conclusion = conclusion.strip()
        if not conclusion:
            raise RDRError("Kesimpulan baru tidak boleh kosong.")
        result = self.infer(case)
        if conclusion == result.conclusion:
            raise RDRError("Kesimpulan baru sama dengan kesimpulan sistem; tidak perlu rule baru.")
        self.validate_conditions(case, self.cornerstone_for(result), conditions)

        node = Node(
            id=self._next_id,
            conditions=list(conditions),
            conclusion=conclusion,
            cornerstone=dict(case),
            parent=result.attach_parent_id,
        )
        parent = self.nodes[result.attach_parent_id]
        if result.attach_side == "true":
            parent.true_child = node.id
        else:
            parent.false_child = node.id
        self.nodes[node.id] = node
        self._next_id += 1
        return node

    def log(self, case: dict, system_conclusion: str, final_conclusion: str, accepted: bool, new_rule_id: int | None = None) -> None:
        self.history.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "case": dict(case),
            "system_conclusion": system_conclusion,
            "final_conclusion": final_conclusion,
            "accepted": accepted,
            "new_rule_id": new_rule_id,
        })

    # ---------- utilitas ----------
    def conclusions(self) -> list[str]:
        seen: list[str] = []
        for n in self.nodes.values():
            if n.conclusion not in seen:
                seen.append(n.conclusion)
        return seen

    def side_of(self, node_id: int) -> str | None:
        node = self.nodes[node_id]
        if node.parent is None:
            return None
        return "true" if self.nodes[node.parent].true_child == node_id else "false"

    def to_dict(self) -> dict:
        return {
            "next_id": self._next_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeBase":
        nodes = {n["id"]: Node.from_dict(n) for n in d["nodes"]}
        if 0 not in nodes:
            raise RDRError("File KB tidak valid: Rule 0 tidak ditemukan.")
        kb = cls(nodes[0].conclusion)
        kb.nodes = nodes
        kb.history = d.get("history", [])
        kb._next_id = d.get("next_id", max(nodes) + 1)
        return kb

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeBase":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
