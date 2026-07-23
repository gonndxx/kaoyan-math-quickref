"""Structural, rendering and representative symbolic checks for the formula bank."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import sympy as sp

from formulas import CHAPTER_ORDER, FORMULAS, SOURCES, SUBJECT_ORDER


ROOT = Path(__file__).resolve().parent


def structural_checks() -> list[str]:
    errors: list[str] = []
    ids = [card["id"] for card in FORMULAS]
    duplicates = [key for key, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f"重复 ID: {duplicates}")

    allowed_subjects = set(SUBJECT_ORDER)
    allowed_chapters = {
        (subject, chapter)
        for subject, chapters in CHAPTER_ORDER.items()
        for chapter in chapters
    }
    required = {
        "id", "subject", "chapter", "title", "latex", "when",
        "conditions", "pitfalls", "keywords", "priority", "copyText",
        "aliases", "problemTypes", "questionSignals", "avoidWhen",
        "decisionSteps", "sourceRefs", "scopeVersion", "verifiedAt", "tier",
    }
    source_ids = {source["id"] for source in SOURCES}
    if len(source_ids) != len(SOURCES):
        errors.append("资料来源 ID 重复")
    for card in FORMULAS:
        missing = required - set(card)
        if missing:
            errors.append(f"{card.get('id', '?')}: 缺字段 {sorted(missing)}")
            continue
        if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d{3}", card["id"]):
            errors.append(f"{card['id']}: ID 格式错误")
        if card["subject"] not in allowed_subjects:
            errors.append(f"{card['id']}: 未知科目 {card['subject']}")
        if (card["subject"], card["chapter"]) not in allowed_chapters:
            errors.append(f"{card['id']}: 章节不在覆盖清单")
        for field in ("title", "latex", "when", "copyText"):
            if not str(card[field]).strip():
                errors.append(f"{card['id']}: {field} 为空")
        for field in ("conditions", "pitfalls", "keywords"):
            if not card[field] or not all(str(value).strip() for value in card[field]):
                errors.append(f"{card['id']}: {field} 为空")
        for field in ("questionSignals", "avoidWhen", "decisionSteps", "sourceRefs"):
            if not card[field] or not all(str(value).strip() for value in card[field]):
                errors.append(f"{card['id']}: {field} 为空")
        if card["tier"] not in {"核心", "重要", "扩展"}:
            errors.append(f"{card['id']}: 未知权重 {card['tier']}")
        unknown_sources = set(card["sourceRefs"]) - source_ids
        if unknown_sources:
            errors.append(f"{card['id']}: 未知来源 {sorted(unknown_sources)}")

    for subject, chapters in CHAPTER_ORDER.items():
        for chapter in chapters:
            if not any(c["subject"] == subject and c["chapter"] == chapter for c in FORMULAS):
                errors.append(f"覆盖缺口: {subject} / {chapter}")
    return errors


def symbolic_checks() -> list[str]:
    errors: list[str] = []
    x, a, p = sp.symbols("x a p", positive=True)

    checks = {
        "sinx/x 极限": sp.limit(sp.sin(x) / x, x, 0) == 1,
        "(1-cosx)/x² 极限": sp.limit((1 - sp.cos(x)) / x**2, x, 0) == sp.Rational(1, 2),
        "ln(1+x)/x 极限": sp.limit(sp.log(1 + x) / x, x, 0) == 1,
        "(x-sinx)/x³ 极限": sp.limit((x - sp.sin(x)) / x**3, x, 0) == sp.Rational(1, 6),
        "(tanx-x)/x³ 极限": sp.limit((sp.tan(x) - x) / x**3, x, 0) == sp.Rational(1, 3),
        "(arcsinx-x)/x³ 极限": sp.limit((sp.asin(x) - x) / x**3, x, 0) == sp.Rational(1, 6),
        "(x-arctanx)/x³ 极限": sp.limit((x - sp.atan(x)) / x**3, x, 0) == sp.Rational(1, 3),
        "余弦四阶主部": sp.limit(
            (1 - sp.cos(x) - x**2 / 2) / x**4, x, 0
        ) == -sp.Rational(1, 24),
        "arcsin 七阶展开": sp.series(sp.asin(x), x, 0, 9).removeO()
        == x + x**3 / 6 + 3 * x**5 / 40 + 5 * x**7 / 112,
        "arctan 七阶展开": sp.series(sp.atan(x), x, 0, 9).removeO()
        == x - x**3 / 3 + x**5 / 5 - x**7 / 7,
        "幂指求导": sp.simplify(
            sp.diff(x**x, x) - x**x * (sp.log(x) + 1)
        ) == 0,
        "反正切积分": sp.simplify(sp.diff(sp.atan(x), x) - 1 / (1 + x**2)) == 0,
        "球坐标 Jacobian": sp.simplify(
            sp.Matrix([
                sp.symbols("rho") * sp.sin(sp.symbols("phi")) * sp.cos(sp.symbols("theta")),
                sp.symbols("rho") * sp.sin(sp.symbols("phi")) * sp.sin(sp.symbols("theta")),
                sp.symbols("rho") * sp.cos(sp.symbols("phi")),
            ]).jacobian(sp.symbols("rho phi theta")).det() ** 2
            - sp.symbols("rho") ** 4 * sp.sin(sp.symbols("phi")) ** 2
        ) == 0,
        "二项均值": sp.summation(
            sp.symbols("k", integer=True, nonnegative=True)
            * sp.binomial(5, sp.symbols("k", integer=True, nonnegative=True))
            * p ** sp.symbols("k", integer=True, nonnegative=True)
            * (1 - p) ** (5 - sp.symbols("k", integer=True, nonnegative=True)),
            (sp.symbols("k", integer=True, nonnegative=True), 0, 5),
        ).simplify() == 5 * p,
        "指数密度归一": sp.integrate(a * sp.exp(-a * x), (x, 0, sp.oo)) == 1,
        "指数均值": sp.integrate(x * a * sp.exp(-a * x), (x, 0, sp.oo)) == 1 / a,
        "样本离差恒等式": sp.expand(
            sum((value - sp.Symbol("xb")) ** 2 for value in sp.symbols("x1:5"))
            - (
                sum(value**2 for value in sp.symbols("x1:5"))
                - 4 * sp.Symbol("xb") ** 2
            )
        ).subs(
            sp.Symbol("xb"), sum(sp.symbols("x1:5")) / 4
        ).simplify() == 0,
    }

    # Representative finite-dimensional identities.
    matrix = sp.Matrix([[2, 1, 0], [0, 3, 4], [5, 0, 1]])
    checks["伴随恒等式"] = matrix * matrix.adjugate() == matrix.det() * sp.eye(3)
    checks["伴随行列式"] = matrix.adjugate().det() == matrix.det() ** 2
    values = [sp.Integer(1), sp.Integer(2), sp.Integer(4)]
    vandermonde = sp.Matrix([[value**power for value in values] for power in range(3)])
    checks["范德蒙"] = vandermonde.det() == sp.prod(
        values[j] - values[i] for i in range(3) for j in range(i + 1, 3)
    )

    wallis4 = sp.integrate(sp.sin(x) ** 4, (x, 0, sp.pi / 2))
    checks["华里士 n=4"] = wallis4 == sp.Rational(3, 16) * sp.pi

    for name, passed in checks.items():
        if not bool(passed):
            errors.append(f"符号核验失败: {name}")
    return errors


def katex_check(node: str, katex_root: Path) -> tuple[bool, str]:
    payload = json.dumps(
        [{"id": card["id"], "latex": card["latex"]} for card in FORMULAS],
        ensure_ascii=False,
    )
    result = subprocess.run(
        [node, str(ROOT / "validate_katex.js"), str(katex_root)],
        input=payload,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True)
    parser.add_argument("--katex-root", required=True, type=Path)
    args = parser.parse_args()

    errors = structural_checks()
    errors.extend(symbolic_checks())
    katex_ok, katex_output = katex_check(args.node, args.katex_root)
    if not katex_ok:
        errors.append(katex_output)

    counts = Counter(card["subject"] for card in FORMULAS)
    print(
        f"结构: {len(FORMULAS)} 个主题 / {len(CHAPTER_ORDER)} 个科目 / "
        f"{sum(len(v) for v in CHAPTER_ORDER.values())} 个章节"
    )
    print("科目:", "，".join(f"{key} {counts[key]}" for key in SUBJECT_ORDER))
    if katex_output:
        print(katex_output)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    print("符号核验: 代表性高风险公式全部通过。")
    print("内容结构校验: 通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
