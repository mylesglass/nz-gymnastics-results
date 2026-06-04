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

    # Build wide data once then split by discipline
    sentinel = -999999.0
    df["aa_score"] = df["aa_score"].fillna(sentinel)

    score_cols = ["d_score", "e_score", "n_score", "total_score"]
    agg_map = {c: "mean" for c in score_cols}
    agg_map["apparatus_rank"] = "first"
    agg_map["gnz_id"] = "first"
    agg_map["club_name"] = "first"
    agg_map["level_category"] = "first"
    agg_map["division"] = "first"

    grouped = df.groupby(
        ["gymnast_name", "round_type", "aa_score", "apparatus"], sort=False, dropna=False
    ).agg(agg_map).reset_index()

    pivot = grouped.pivot_table(
        index=["gymnast_name", "round_type"],
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

    meta = df.drop_duplicates(subset=["gymnast_name", "round_type"], keep="first")[
        ["gymnast_name", "round_type", "aa_score", "gnz_id", "club_name", "level_category",
         "division", "aa_rank"]
    ].copy()

    combined = pivot.merge(meta, on=["gymnast_name", "round_type"], how="left", suffixes=("", "_y"))
    for col in list(combined.columns):
        if col.endswith("_y"):
            del combined[col]

    combined["aa_score"] = combined["aa_score"].replace(sentinel, None)
    combined.rename(columns={
        "gymnast_name": "name",
        "gnz_id": "gnz-id",
        "club_name": "club",
        "level_category": "step",
        "aa_rank": "aa-rank",
        "aa_score": "aa-score",
        "round_type": "round-type",
        "division": "division",
    }, inplace=True)

    all_rows = combined.to_dict(orient="records")

    # Convert NaN to None for JSON compliance
    for row in all_rows:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None

    for disc_key, prefixes in [("wag", ["vt", "ub", "bb", "fx"]), ("mag", ["fx", "ph", "sr", "vt", "pb", "hb"])]:
        if (disc_key == "wag" and not has_wag) or (disc_key == "mag" and not has_mag):
            continue

        columns = _wide_column_list_for_prefixes(prefixes, present_apps)
        seen = set()
        out_rows = []
        for row in all_rows:
            if any(row.get(f"{p}-total") is not None for p in prefixes):
                key = (row.get("name"), row.get("round-type"))
                if key not in seen:
                    seen.add(key)
                    out_row = _build_wide_row(row, prefixes, columns)
                    out_rows.append(out_row)

        result[disc_key] = {"columns": columns, "rows": out_rows}

    return result


def _build_wide_row(row: dict, prefixes: list[str], columns: list[str]) -> dict:
    """Build a wide row, filling missing apparatus with DNS and handling AA DNF."""
    out = {}

    completed_total = 0.0
    completed_count = 0
    expected_count = len(prefixes)

    for p in prefixes:
        total = row.get(f"{p}-total")
        rank = row.get(f"{p}-rank")
        d = row.get(f"{p}-d")
        e = row.get(f"{p}-e")
        n = row.get(f"{p}-n")

        if total is not None:
            completed_total += float(total)
            completed_count += 1
            out[f"{p}-total"] = _fmt3(total)
            out[f"{p}-d"] = _fmt1(d) if d is not None else None
            out[f"{p}-e"] = _fmt3(e) if e is not None else None
            out[f"{p}-n"] = _fmt1(n) if n is not None else 0.0
            out[f"{p}-rank"] = rank
        else:
            out[f"{p}-total"] = "DNS"
            out[f"{p}-d"] = None
            out[f"{p}-e"] = None
            out[f"{p}-n"] = None
            out[f"{p}-rank"] = "DNS"

    # AA handling
    aa_score = row.get("aa-score")
    aa_rank = row.get("aa-rank")

    if aa_score is not None:
        out["aa-score"] = _fmt3(aa_score)
        out["aa-rank"] = aa_rank
    elif completed_count < expected_count and completed_count > 0:
        out["aa-score"] = _fmt3(completed_total)
        out["aa-rank"] = "DNF"
    else:
        out["aa-score"] = None
        out["aa-rank"] = None

    # Copy metadata columns
    for col in columns:
        if col not in out:
            if col == "round-type":
                out[col] = row.get("round-type", "")
            else:
                out[col] = row.get(col)

    return out


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