from __future__ import annotations

import pandas as pd

import A_config
import C_client


TICKER = "SPGI"
TARGET_DATE = "2024-12-31"

pd.set_option("display.max_columns", 80)
pd.set_option("display.width", 240)
pd.set_option("display.max_rows", 200)


def main() -> None:
    cik = A_config.get_cik(TICKER)
    positions = A_config.get_flat_financial_positions_for_ticker(TICKER)

    rows = []

    with C_client.make_session() as session:
        companyfacts = C_client.fetch_companyfacts(
            session=session,
            ticker=TICKER,
            cik=cik,
        )

    for position in positions:
        for concept in A_config.get_concepts_for_financial_position(TICKER, position):
            facts = C_client.facts_for_concept(companyfacts, concept)
            df = pd.DataFrame(facts)

            if df.empty:
                continue

            df["end"] = pd.to_datetime(df.get("end"), errors="coerce")
            df["start"] = pd.to_datetime(df.get("start"), errors="coerce")
            df["filed"] = pd.to_datetime(df.get("filed"), errors="coerce")
            df["duration_days"] = (df["end"] - df["start"]).dt.days

            matches = df[
                (df["unit"] == A_config.TARGET_CURRENCY)
                & (df["end"].dt.strftime("%Y-%m-%d") == TARGET_DATE)
            ].copy()

            for _, fact in matches.iterrows():
                rows.append(
                    {
                        "position": position,
                        "concept": concept,
                        "accn": fact.get("accn"),
                        "form": fact.get("form"),
                        "value": fact.get("val"),
                        "unit": fact.get("unit"),
                        "start": fact.get("start"),
                        "end": fact.get("end"),
                        "duration_days": fact.get("duration_days"),
                        "filed": fact.get("filed"),
                        "frame": fact.get("frame"),
                    }
                )

    result = pd.DataFrame(rows)

    if result.empty:
        print(f"No USD companyfacts found with end date {TARGET_DATE}.")
        return

    result = result.sort_values(
        ["position", "concept", "duration_days", "filed"],
        ascending=[True, True, False, False],
    )

    print(result.to_string(index=False))


if __name__ == "__main__":
    main()