"""Transform long-format SQLite data into wide-format rows for display/export."""

import io

import pandas as pd

from app.models import LongScore

WAG_ORDER = ["VT", "UB", "BB", "FX"]
MAG_ORDER = ["FX", "PH", "SR", "VT", "PB", "HB"]
_SCORE_SHORT = {"d_score": "d", "e_score": "e", "n_score": "n", "total_score": "total"}


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


def pivot_to_wide(event_id: int, session, event_name: str, event_date: str) -> pd.DataFrame:
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
        app, metric = col
        if metric == "apparatus_rank":
            flat_cols.append(f"{app.lower()}-rank")
        else:
            flat_cols.append(f"{app.lower()}-{_SCORE_SHORT.get(metric, metric)}")
    pivot.columns = flat_cols
    pivot = pivot.reset_index()

    # Merge metadata
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

    return result[[c for c in expected if c in result.columns]]


def export_csv(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    return buf.getvalue()