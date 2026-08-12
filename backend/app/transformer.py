"""Transform long-format SQLite data into wide-format rows for display/export."""

import io
import json
import math

import numpy as np
import pandas as pd

from app.cache import cached
from app.clubdata import ensure_seed
from app.models import LongScore

_CLUB_DATA: dict | None = None


def _load_club_data():
    global _CLUB_DATA
    if _CLUB_DATA is None:
        try:
            with open(ensure_seed()) as f:
                _CLUB_DATA = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _CLUB_DATA = {"regions": {}, "lookup": {}}
    return _CLUB_DATA


def _find_region(club_name: str) -> str:
    if not club_name:
        return ""
    club_data = _load_club_data()
    lower = club_name.lower().strip()
    # Direct region name match (e.g. Nationals where org is the region)
    for region_name in club_data.get("regions", {}):
        if lower == region_name.lower():
            return region_name
    v = club_data.get("lookup", {}).get(lower)
    if v:
        region = v.get("region")
        if region:
            return region
        return _region_from_canonical(v["name"], club_data)
    return _region_from_prefix(lower, club_data)


def _region_from_canonical(canonical: str, club_data: dict) -> str:
    for region_name, clubs in club_data.get("regions", {}).items():
        for c in clubs:
            if c["name"].lower() == canonical.lower():
                return region_name
    return ""


def _region_from_prefix(lower: str, club_data: dict) -> str:
    for region_name, clubs in club_data.get("regions", {}).items():
        for c in clubs:
            for name in [c["name"]] + c.get("aliases", []):
                ln = name.lower()
                if lower.startswith(ln) or ln.startswith(lower):
                    return region_name
    return ""


def _guess_host_club(event_name: str) -> str:
    """Best-effort host-club guess from an event name.

    Matches canonical club names and aliases as substrings of the event name
    (case-insensitive); the longest match wins. Returns ``""`` when nothing
    matches (Nationals should be set to ``"Gymnastics NZ"`` separately).
    """
    if not event_name:
        return ""
    lower = event_name.lower()
    club_data = _load_club_data()
    best = ""
    best_len = 0
    for region_name, clubs in club_data.get("regions", {}).items():
        for c in clubs:
            canonical = c["name"]
            for name in [canonical] + c.get("aliases", []):
                ln = name.lower()
                if ln and ln in lower and len(ln) > best_len:
                    best = canonical
                    best_len = len(ln)
    return best

WAG_ORDER = ["VT", "UB", "BB", "FX"]
MAG_ORDER = ["FX", "PH", "SR", "VT", "PB", "HB"]


def pivot_to_wide(event_id: int, session, event_name: str, event_date: str) -> pd.DataFrame:
    """Pivot to wide format (used for CSV/XLSX exports).

    Includes all available columns: meta, apparatus display scores,
    per-pass vault details, bonus, division, round_type.
    """
    wide = pivot_to_wide_dict(event_id, session)
    if not wide:
        return pd.DataFrame()

    all_rows: list[dict] = []
    for disc_key in ["wag", "mag"]:
        if disc_key not in wide:
            continue
        for row in wide[disc_key]["rows"]:
            row["competition"] = event_name
            row["date-created"] = event_date
            all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Build column order: meta, apparatus, aa
    meta_cols = [
        "gnz-id", "name", "club", "region", "step", "division", "round-type",
        "competition", "date-created",
    ]
    app_cols = [c for c in df.columns if c not in meta_cols and c not in ("aa-score", "aa-rank")]
    # Only vault has multiple passes — hide per-pass columns for other apparatus
    app_cols = [c for c in app_cols if not ('-1-' in c or '-2-' in c) or c.startswith('vt-')]
    ordered = meta_cols + sorted(app_cols) + ["aa-score", "aa-rank"]

    for col in ordered:
        if col not in df.columns:
            df[col] = None

    # Convert NaN to None
    for col in df.columns:
        if df[col].dtype == "float64":
            df[col] = df[col].where(df[col].notna(), None)

    return df[[c for c in ordered if c in df.columns]]


def pivot_to_wide_dict(event_id: int, session, gnz_id: str = None, club: str = None) -> dict:
    return cached(
        ("event", event_id, "pivot", gnz_id or "", club or ""),
        lambda: _compute_pivot(event_id, session, gnz_id, club),
    )


def pivot_to_wide_dict_multi(event_ids: list[int], session, gnz_id: str = None, club: str = None) -> dict:
    return _compute_pivot_multi(event_ids, session, gnz_id, club)


def _long_rows_from_session(query) -> list[dict]:
    scores = query.all()
    if not scores:
        return []
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
            "bonus": s.bonus,
        })
    return long_rows


def _compute_pivot(event_id: int, session, gnz_id: str = None, club: str = None) -> dict:
    """Pivot long-format scores into wide-format rows per discipline.

    Returns dict: {wag: {columns, rows}, mag: {columns, rows}}
    """
    query = session.query(LongScore).filter(LongScore.event_id == event_id)
    if gnz_id:
        query = query.filter(LongScore.gnz_id == gnz_id)
    if club:
        query = query.filter(LongScore.club_name == club)
    long_rows = _long_rows_from_session(query)
    if not long_rows:
        return {}
    return _pivot_long_rows(long_rows)


def _compute_pivot_multi(event_ids: list[int], session, gnz_id: str = None, club: str = None) -> dict:
    query = session.query(LongScore).filter(LongScore.event_id.in_(event_ids))
    if gnz_id:
        query = query.filter(LongScore.gnz_id == gnz_id)
    if club:
        query = query.filter(LongScore.club_name == club)
    scores = query.all()
    if not scores:
        return {}

    rows_by_event: dict[int, list[dict]] = {}
    event_names: dict[int, str] = {}
    for s in scores:
        rows_by_event.setdefault(s.event_id, []).append(s)
        if s.event_id not in event_names:
            event_names[s.event_id] = s.event_name or ""

    combined: dict[str, dict] = {}
    for event_id in event_ids:
        if event_id not in rows_by_event:
            continue
        event_scores = rows_by_event[event_id]
        long_rows = []
        for s in event_scores:
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
                "bonus": s.bonus,
            })
        data = _pivot_long_rows(long_rows)
        if not data:
            continue
        event_name = event_names.get(event_id, "")
        for disc_key in ("wag", "mag"):
            if disc_key not in data:
                continue
            if disc_key not in combined:
                combined[disc_key] = {"columns": [], "rows": []}
            disc = data[disc_key]
            for row in disc["rows"]:
                row["event_name"] = event_name
                row["event_id"] = event_id
            combined[disc_key]["rows"].extend(disc["rows"])
            if not combined[disc_key]["columns"]:
                combined[disc_key]["columns"] = list(disc["columns"])
            else:
                for c in disc["columns"]:
                    if c not in combined[disc_key]["columns"]:
                        combined[disc_key]["columns"].append(c)

    for disc_key in combined:
        if "event_name" in combined[disc_key]["columns"]:
            combined[disc_key]["columns"].remove("event_name")
        combined[disc_key]["columns"].insert(0, "event_name")

    return combined


def _pivot_long_rows(long_rows: list[dict]) -> dict:
    """Core pivot logic: given long-format rows, return wide-format per discipline."""
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
         "division", "aa_rank", "discipline"]
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
            wide_row["discipline"] = mr.get("discipline", "")

        for app, passes in scores.items():
            pfx = app.lower()
            if len(passes) == 1:
                p = passes[0]
                wide_row[f"{pfx}-total"] = p.get("total_score")
                wide_row[f"{pfx}-d"] = p.get("d_score")
                wide_row[f"{pfx}-e"] = p.get("e_score")
                wide_row[f"{pfx}-n"] = p.get("n_score")
                wide_row[f"{pfx}-rank"] = p.get("apparatus_rank")
                wide_row[f"{pfx}-bonus"] = p.get("bonus")
            else:
                for i, p in enumerate(passes, 1):
                    wide_row[f"{pfx}-{i}-total"] = p.get("total_score")
                    wide_row[f"{pfx}-{i}-d"] = p.get("d_score")
                    wide_row[f"{pfx}-{i}-e"] = p.get("e_score")
                    wide_row[f"{pfx}-{i}-n"] = p.get("n_score")
                    wide_row[f"{pfx}-{i}-rank"] = p.get("apparatus_rank")
                    wide_row[f"{pfx}-{i}-bonus"] = p.get("bonus")
                # Grab bonus from any pass (it's the same across the group)
                wide_row[f"{pfx}-bonus"] = passes[0].get("bonus")

        wide_rows.append(wide_row)

    all_rows = wide_rows

    # Convert NaN to None for JSON compliance
    for row in all_rows:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
            elif isinstance(v, np.integer):
                row[k] = int(v)
            elif isinstance(v, np.floating):
                row[k] = float(v)
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
        row["region"] = _find_region(row.get("club", ""))

    for disc_key, prefixes in [("wag", ["vt", "ub", "bb", "fx"]), ("mag", ["fx", "ph", "sr", "vt", "pb", "hb"])]:
        if (disc_key == "wag" and not has_wag) or (disc_key == "mag" and not has_mag):
            continue

        columns = _wide_column_list_for_prefixes(prefixes, present_apps)
        seen = set()
        out_rows = []
        for row in all_rows:
            row_disc = str(row.get("discipline", "")).upper()
            if disc_key == "wag":
                if row_disc not in ("WAG", "WAG+MAG"):
                    continue
            else:
                if row_disc not in ("MAG", "WAG+MAG"):
                    continue
            key = (row.get("name"), row.get("round-type"))
            if key not in seen:
                seen.add(key)
                out_row = _build_wide_row(row, prefixes, columns)

                # Apparatus finals / Day 2: AA = sum of apparatus scored in this round
                rt_lower = str(row.get("round-type", "")).lower()
                if "apparatus finals" in rt_lower or "day 2" in rt_lower:
                    aa_sum = 0.0
                    for p in prefixes:
                        total = out_row.get(f"{p}-total")
                        if total is not None and total != "DNS":
                            aa_sum += float(total)
                    out_row["aa-score"] = _fmt3(aa_sum) if aa_sum > 0 else None
                    out_row["aa-rank"] = None

                # Skip rows where no apparatus has a real score
                if any(out_row.get(f"{p}-total") not in (None, "DNS") for p in prefixes):
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
            out[f"{p}-bonus"] = row.get(f"{p}-bonus")
        elif pass1_total is not None or row.get(f"{p}-2-total") is not None:
            # Multi-pass — collect raw values
            p1_total = pass1_total
            p1_d = row.get(f"{p}-1-d")
            p1_e = row.get(f"{p}-1-e")
            p1_n = row.get(f"{p}-1-n")
            p1_r = row.get(f"{p}-1-rank")
            p1_bonus = row.get(f"{p}-1-bonus")

            p2_total = row.get(f"{p}-2-total")
            p2_d = row.get(f"{p}-2-d")
            p2_e = row.get(f"{p}-2-e")
            p2_n = row.get(f"{p}-2-n")
            p2_r = row.get(f"{p}-2-rank")
            p2_bonus = row.get(f"{p}-2-bonus")

            # Determine display aggregation rule
            if p1_total is None:
                # Pass 1 is a DNS/placeholder pass (no final score) — use pass 2
                best_total = float(p2_total)
                best_d = p2_d
                best_e = p2_e
                best_n = p2_n
            elif p2_total is None:
                # Only one vault recorded — use it directly
                best_total = float(p1_total)
                best_d = p1_d
                best_e = p1_e
                best_n = p1_n
            else:
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
            out[f"{p}-bonus"] = row.get(f"{p}-bonus")

            # Write per-pass columns
            for prefix_val, p_total, p_d, p_e, p_n, p_r, p_bonus in [
                (f"{p}-1", p1_total, p1_d, p1_e, p1_n, p1_r, p1_bonus),
                (f"{p}-2", p2_total, p2_d, p2_e, p2_n, p2_r, p2_bonus),
            ]:
                if p_total is not None:
                    out[f"{prefix_val}-total"] = _fmt3(p_total)
                    out[f"{prefix_val}-d"] = _fmt1(p_d) if p_d is not None else None
                    out[f"{prefix_val}-e"] = _fmt3(p_e) if p_e is not None else None
                    out[f"{prefix_val}-n"] = _fmt1(p_n) if p_n is not None else 0.0
                    out[f"{prefix_val}-rank"] = p_r
                    out[f"{prefix_val}-bonus"] = p_bonus
                else:
                    out[f"{prefix_val}-total"] = "DNS"
                    out[f"{prefix_val}-d"] = None
                    out[f"{prefix_val}-e"] = None
                    out[f"{prefix_val}-n"] = None
                    out[f"{prefix_val}-rank"] = "DNS"
                    out[f"{prefix_val}-bonus"] = None
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
    elif completed_count > 0:
        out["aa-score"] = _fmt3(completed_total)
        out["aa-rank"] = "DNF" if completed_count < expected_count else None
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
    """Determine if multi-pass vault should average (True) or take higher (False).

    Rules:
      STEP 6 & 7:                always average both vaults
      STEP 10, Senior Int,
      Junior Int, Youth
      on Apparatus Finals day:   average both vaults
      STEP 10, Senior Int,
      Junior Int
      on All Around day:         best mark (take the higher)
      Youth
      on All Around day:         best mark (take the higher)
      Everything else:           best mark
    """
    lower_step = step.lower()
    lower_rt = (round_type or "").lower()

    if "step 6" in lower_step or "step 7" in lower_step:
        return True

    is_high_level = any(x in lower_step for x in [
        "step 10", "senior international", "junior international", "youth",
    ])
    if not is_high_level:
        return False

    is_apparatus_day = "apparatus" in lower_rt or "final" in lower_rt
    if is_apparatus_day:
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
        v = round(float(val), 6)
        return f"{math.floor(v * 1000) / 1000:.3f}"
    except (ValueError, TypeError):
        return str(val)


def _wide_column_list_for_prefixes(prefixes: list[str], present_apps: set[str]) -> list[str]:
    cols = ["gnz-id", "name", "club", "region", "step", "division", "round-type"]
    suffixes = ["total", "d", "e", "n", "rank", "bonus"]
    for prefix in prefixes:
        for suffix in suffixes:
            cols.append(f"{prefix}-{suffix}")
        if prefix == "vt":
            for pass_num in (1, 2):
                for suffix in suffixes:
                    cols.append(f"{prefix}-{pass_num}-{suffix}")
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