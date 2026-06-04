"""Transform long-format SQLite data into wide-format rows for display/export."""

import io

import math
import pandas as pd

from app.models import LongScore

WAG_ORDER = ["VT", "UB", "BB", "FX"]
MAG_ORDER = ["FX", "PH", "SR", "VT", "PB", "HB"]
_SCORE_SHORT = {"d_score": "d", "e_score": "e", "n_score": "n", "total_score": "total"}


def pivot_to_wide(event_id: int, session, event_name: str, event_date: str) -> pd.DataFrame:
    """Pivot to wide format (used for CSV/XLSX exports)."""
    scores = (
        session.query(LongScore)
        .filter(LongScore.event_id == event_id)
        .all()
    )
    if not scores:
        return pd.DataFrame()

    rows = []
    for s in scores:
        rows.append({
            "gymnast_name": s.gymnast_name,
            "gnz_id": s.gnz_id or "",
            "club_name": s.club_name or "",
            "discipline": s.discipline,
            "level_category": s.level_category or "",
            "apparatus": s.apparatus,
            "d_score": s.d_score,
            "e_score": s.e_score,
            "n_score": s.neutral_deductions,
            "total_score": s.pass_final_score,
            "apparatus_rank": s.apparatus_rank,
            "aa_score": s.aa_score,
            "aa_rank": s.aa_rank,
        })

    df = pd.DataFrame(rows)
    present_apps = sorted(set(df["apparatus"].unique()))
    apparatus_order = _determine_apparatus_order(set(present_apps))

    sentinel = -999999.0
    df["aa_score"] = df["aa_score"].fillna(sentinel)

    score_cols = ["d_score", "e_score", "n_score", "total_score"]
    agg_map = {c: "mean" for c in score_cols}
    agg_map["apparatus_rank"] = "first"
    agg_map["gnz_id"] = "first"
    agg_map["club_name"] = "first"
    agg_map["level_category"] = "first"

    grouped = df.groupby(
        ["gymnast_name", "aa_score", "apparatus"], sort=False, dropna=False
    ).agg(agg_map).reset_index()

    pivot = grouped.pivot_table(
        index=["gymnast_name", "aa_score"],
        columns="apparatus",
        values=score_cols + ["apparatus_rank"],
        aggfunc="first",
    )

    flat_cols = []
    for col in pivot.columns:
        metric, app = col
        if metric == "apparatus_rank":
            flat_cols.append(f"{app.lower()}-rank")
        else:
            short = _SCORE_SHORT.get(metric, metric)
            flat_cols.append(f"{app.lower()}-{short}")
    pivot.columns = flat_cols
    pivot = pivot.reset_index()

    meta = df.drop_duplicates(subset=["gymnast_name", "aa_score"], keep="first")[
        ["gymnast_name", "aa_score", "gnz_id", "club_name", "level_category", "aa_rank"]
    ].copy()

    result = pivot.merge(meta, on=["gymnast_name", "aa_score"], how="left", suffixes=("", "_y"))
    for col in list(result.columns):
        if col.endswith("_y"):
            del result[col]

    result["aa_score"] = result["aa_score"].replace(sentinel, None)
    result.rename(columns={
        "gymnast_name": "name",
        "gnz_id": "gnz-id",
        "club_name": "club",
        "level_category": "step",
        "aa_rank": "aa-rank",
        "aa_score": "aa-score",
    }, inplace=True)

    result["competition"] = event_name
    result["date-created"] = event_date

    expected = ["gnz-id", "name", "club", "step", "competition", "date-created"]
    for app in apparatus_order:
        for suffix in ["total", "d", "e", "n", "rank"]:
            expected.append(f"{app.lower()}-{suffix}")
    expected.extend(["aa-score", "aa-rank"])

    for col in expected:
        if col not in result.columns:
            result[col] = None

    # Convert NaN to None
    for col in result.columns:
        if result[col].dtype == "float64":
            result[col] = result[col].where(result[col].notna(), None)

    return result[[c for c in expected if c in result.columns]]


def _determine_apparatus_order(present_apps: set[str]) -> list[str]:
    has_mag = any(a in present_apps for a in ["PH", "SR", "PB", "HB"])
    has_wag = any(a in present_apps for a in ["UB", "BB"])
    result = []
    if has_wag:
        result.extend(WAG_ORDER)
    if has_mag:
        for a in MAG_ORDER:
            if a not in result:
                result.append(a)
    return [a for a in result if a in present_apps]


def pivot_to_wide_dict(event_id: int, session) -> dict:
    """Pivot long-format scores into wide-format rows per discipline.

    Returns dict: {wag: {columns, rows}, mag: {columns, rows}}
    """
    scores = (
        session.query(LongScore)
        .filter(LongScore.event_id == event_id)
        .all()
    )
    if not scores:
        return {}

    long_rows = []
    for s in scores:
        long_rows.append({
            "gymnast_name": s.gymnast_name,
            "gnz_id": s.gnz_id or "",
            "club_name": s.club_name or "",
            "discipline": s.discipline,
            "level_category": s.level_category or "",
            "division": s.division or "",
            "round_type": s.round_type or "",
            "apparatus": s.apparatus,
            "d_score": s.d_score,
            "e_score": s.e_score,
            "n_score": s.neutral_deductions,
            "total_score": s.pass_final_score,
            "apparatus_rank": s.apparatus_rank,
            "aa_score": s.aa_score,
            "aa_rank": s.aa_rank,
        })

    df = pd.DataFrame(long_rows)
    present_apps = set(df["apparatus"].unique())

    has_wag = any(a in present_apps for a in ["UB", "BB"])
    has_mag = any(a in present_apps for a in ["PH", "SR", "PB", "HB"])

    result: dict[str, dict] = {}

# Group raw data without averaging scores — keep per-pass info
    # Build a dict: (gymnast_name, round_type) -> {apparatus -> [pass_rows]}
    gymnast_round_scores: dict = {}
    for _, row in df.iterrows():
        key = (row["gymnast_name"], row["round_type"])
        if key not in gymnast_round_scores:
            gymnast_round_scores[key] = {}
        app = row["apparatus"]
        if app not in gymnast_round_scores[key]:
            gymnast_round_scores[key][app] = []
        gymnast_round_scores[key][app].append(row)

    # Build wide rows manually
    meta = df.drop_duplicates(subset=["gymnast_name", "round_type"], keep="first")[
        ["gymnast_name", "round_type", "aa_score", "gnz_id", "club_name", "level_category",
         "division", "aa_rank"]
    ].copy()
    sentinel = -999999.0
    meta["aa_score"] = meta["aa_score"].fillna(sentinel)

    wide_rows: list[dict] = []
    for (name, rt), scores in gymnast_round_scores.items():
        wide_row: dict[str, object] = {
            "gymnast_name": name,
            "round_type": rt,
        }

        # Sort passes within each apparatus by pass_number
        for app in scores:
            scores[app].sort(key=lambda r: r.get("pass_number", 1))

        # Find metadata for this (name, rt) pair
        meta_row = meta[(meta["gymnast_name"] == name) & (meta["round_type"] == rt)]
        if not meta_row.empty:
            mr = meta_row.iloc[0]
            wide_row["gnz_id"] = mr.get("gnz_id", "")
            wide_row["club_name"] = mr.get("club_name", "")
            wide_row["level_category"] = mr.get("level_category", "")
            wide_row["division"] = mr.get("division", "")
            wide_row["aa_score"] = mr.get("aa_score", sentinel)
            wide_row["aa_rank"] = mr.get("aa_rank")

        for app, passes in scores.items():
            pfx = app.lower()
            if len(passes) == 1:
                p = passes[0]
                wide_row[f"{pfx}-total"] = p.get("total_score")
                wide_row[f"{pfx}-d"] = p.get("d_score")
                wide_row[f"{pfx}-e"] = p.get("e_score")
                wide_row[f"{pfx}-n"] = p.get("n_score")
                wide_row[f"{pfx}-rank"] = p.get("apparatus_rank")
            else:
                for i, p in enumerate(passes, 1):
                    wide_row[f"{pfx}-{i}-total"] = p.get("total_score")
                    wide_row[f"{pfx}-{i}-d"] = p.get("d_score")
                    wide_row[f"{pfx}-{i}-e"] = p.get("e_score")
                    wide_row[f"{pfx}-{i}-n"] = p.get("n_score")
                    wide_row[f"{pfx}-{i}-rank"] = p.get("apparatus_rank")
                # leave display columns as None — _build_wide_row fills them

        wide_rows.append(wide_row)

    all_rows = wide_rows

    # Convert NaN to None for JSON compliance
    for row in all_rows:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
        # Rename columns for _build_wide_row compatibility
        row["name"] = row.pop("gymnast_name")
        row["aa-score"] = row.pop("aa_score", sentinel)
        row["aa-rank"] = row.pop("aa_rank")
        row["round-type"] = row.pop("round_type", "")
        row["gnz-id"] = row.pop("gnz_id", "")
        row["club"] = row.pop("club_name", "")
        row["step"] = row.pop("level_category", "")
        row["competition"] = ""
        row["date-created"] = ""

    for disc_key, prefixes in [("wag", ["vt", "ub", "bb", "fx"]), ("mag", ["fx", "ph", "sr", "vt", "pb", "hb"])]:
        if (disc_key == "wag" and not has_wag) or (disc_key == "mag" and not has_mag):
            continue

        columns = _wide_column_list_for_prefixes(prefixes, present_apps)
        seen = set()
        out_rows = []
        for row in all_rows:
            has_data = any(
                row.get(f"{p}-total") is not None or row.get(f"{p}-1-total") is not None
                for p in prefixes
            )
            if has_data:
                key = (row.get("name"), row.get("round-type"))
                if key not in seen:
                    seen.add(key)
                    out_row = _build_wide_row(row, prefixes, columns)
                    out_rows.append(out_row)

        result[disc_key] = {"columns": columns, "rows": out_rows}

    return result


def _build_wide_row(row: dict, prefixes: list[str], columns: list[str]) -> dict:
    """Build a wide row with per-pass columns, DNS/DNF, and level-aware aggregation."""
    out = {}
    step = str(row.get("step", "")).lower()
    rt = str(row.get("round-type", "")).lower()

    completed_total = 0.0
    completed_count = 0
    expected_count = len(prefixes)

    for p in prefixes:
        total = row.get(f"{p}-total")
        pass1_total = row.get(f"{p}-1-total")

        if total is not None:
            # Single pass
            completed_total += float(total)
            completed_count += 1
            _write_app(out, p, total, row.get(f"{p}-d"), row.get(f"{p}-e"), row.get(f"{p}-n"), row.get(f"{p}-rank"))
        elif pass1_total is not None:
            # Multi-pass — collect raw values
            p1_total = pass1_total
            p1_d = row.get(f"{p}-1-d")
            p1_e = row.get(f"{p}-1-e")
            p1_n = row.get(f"{p}-1-n")
            p1_r = row.get(f"{p}-1-rank")

            p2_total = row.get(f"{p}-2-total")
            p2_d = row.get(f"{p}-2-d")
            p2_e = row.get(f"{p}-2-e")
            p2_n = row.get(f"{p}-2-n")
            p2_r = row.get(f"{p}-2-rank")

            # Determine display aggregation rule
            use_average = _use_vault_average(step, rt)
            if use_average:
                best_total = (float(p1_total) + float(p2_total)) / 2
                best_d = (float(p1_d) + float(p2_d)) / 2 if p1_d is not None and p2_d is not None else None
                best_e = (float(p1_e) + float(p2_e)) / 2 if p1_e is not None and p2_e is not None else None
                best_n = (float(p1_n) + float(p2_n)) / 2 if p1_n is not None and p2_n is not None else 0.0
            else:
                # Higher total wins — use that pass's full score
                if float(p1_total) >= float(p2_total):
                    best_total = float(p1_total)
                    best_d = p1_d
                    best_e = p1_e
                    best_n = p1_n
                else:
                    best_total = float(p2_total)
                    best_d = p2_d
                    best_e = p2_e
                    best_n = p2_n

            best_rank = p1_r or p2_r

            completed_total += best_total
            completed_count += 1
            _write_app(out, p, best_total, best_d, best_e, best_n, best_rank)

            # Write per-pass columns
            for prefix_val, p_total, p_d, p_e, p_n, p_r in [
                (f"{p}-1", p1_total, p1_d, p1_e, p1_n, p1_r),
                (f"{p}-2", p2_total, p2_d, p2_e, p2_n, p2_r),
            ]:
                if p_total is not None:
                    out[f"{prefix_val}-total"] = _fmt3(p_total)
                    out[f"{prefix_val}-d"] = _fmt1(p_d) if p_d is not None else None
                    out[f"{prefix_val}-e"] = _fmt3(p_e) if p_e is not None else None
                    out[f"{prefix_val}-n"] = _fmt1(p_n) if p_n is not None else 0.0
                    out[f"{prefix_val}-rank"] = p_r
                else:
                    out[f"{prefix_val}-total"] = "DNS"
                    out[f"{prefix_val}-d"] = None
                    out[f"{prefix_val}-e"] = None
                    out[f"{prefix_val}-n"] = None
                    out[f"{prefix_val}-rank"] = "DNS"
        else:
            out[f"{p}-total"] = "DNS"
            out[f"{p}-d"] = None
            out[f"{p}-e"] = None
            out[f"{p}-n"] = None
            out[f"{p}-rank"] = "DNS"

    # AA handling
    aa_score = row.get("aa-score")
    aa_rank = row.get("aa-rank")

    if aa_score is not None and aa_score != -999999.0:
        out["aa-score"] = _fmt3(aa_score)
        out["aa-rank"] = aa_rank
    elif completed_count < expected_count and completed_count > 0:
        out["aa-score"] = _fmt3(completed_total)
        out["aa-rank"] = "DNF"
    else:
        out["aa-score"] = None
        out["aa-rank"] = None

    for col in columns:
        if col not in out:
            if col == "round-type":
                out[col] = row.get("round-type", "")
            else:
                out[col] = row.get(col)

    return out


def _use_vault_average(step: str, round_type: str) -> bool:
    """Determine if multi-pass vault should average (True) or take higher (False)."""
    if "step 6" in step or "step 7" in step:
        return True
    if "step 10" in step and "apparatus" in round_type:
        return True
    return False


def _write_app(out: dict, prefix: str, total, d, e, n, rank):
    out[f"{prefix}-total"] = _fmt3(total)
    out[f"{prefix}-d"] = _fmt1(d) if d is not None else None
    out[f"{prefix}-e"] = _fmt3(e) if e is not None else None
    out[f"{prefix}-n"] = _fmt1(n) if n is not None else 0.0
    out[f"{prefix}-rank"] = rank


def _to_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fmt1(val: object) -> str | None:
    if val is None:
        return None
    try:
        return f"{float(val):.1f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt3(val: object) -> str | None:
    if val is None:
        return None
    try:
        return f"{float(val):.3f}"
    except (ValueError, TypeError):
        return str(val)


def _wide_column_list_for_prefixes(prefixes: list[str], present_apps: set[str]) -> list[str]:
    cols = ["gnz-id", "name", "club", "step", "division", "round-type"]
    for prefix in prefixes:
        for suffix in ["total", "d", "e", "n", "rank"]:
            cols.append(f"{prefix}-{suffix}")
    cols.extend(["aa-score", "aa-rank"])
    return cols


def export_csv(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    return buf.getvalue()