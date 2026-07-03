# Memory index

- [Prices & target phase](prices-and-target-phase.md) — daily_prices + target_63d tables, 89-ticker universe, TSM=ADR, risk-free=0
- [KPI values table](kpi-values-table.md) — src/E_kpis.py + kpi_values (raw §2.3 KPIs), computability rules, banks/energy/neg-equity handling
- [Scores table](scores-table.md) — src/F_scores.py + scores (6 sub-scores + financial_score), sector-percentile method, peer-group/NC cautions
- [Operative scores](operative-scores.md) — src/G_operative.py + operative_scores (LLM competitive-advantage 1-5), US 10-K/10-Q + intl 20-F, coverage/gaps
- [A_config CRLF gotcha](aconfig-crlf-gotcha.md) — src/A_config.py is CRLF under autocrlf=true; Edit-tool edits show spurious line-ending diffs, how to commit clean
