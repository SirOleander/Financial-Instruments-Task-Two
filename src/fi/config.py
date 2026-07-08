"""config.py — paths, the company universe, and the risk-free rate.

The part of the old `A_config.py` that a human reads. The ~2,300 lines of literal us-gaap
concept tables now live in `concepts.py` and are re-exported here, so every existing
`A_config.<NAME>` lookup keeps resolving unchanged.

`validate_config()` still runs at import time, exactly as before.
"""
from pathlib import Path

from fi.concepts import (
    CALCULATED_FINANCIAL_ITEMS_BY_GROUP,
    CALCULATED_FINANCIAL_ITEMS_BY_TICKER,
    FINANCIAL_ITEMS_BY_GROUP,
    FINANCIAL_POSITION_SIGN_RULES,
    FINANCIAL_POSITIONS_BY_GROUP,
    INLINE_FINANCIAL_ITEMS_BY_TICKER,
)


BASE_DIR = Path(__file__).resolve().parents[2]   # src/fi/config.py -> repo root
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "financials.db"

SEC_BASE_URL = "https://www.sec.gov"
SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_HEADERS = {"User-Agent": "s5421283@stud.uni-frankfurt.de"}
SEC_SUBMISSIONS_URL_TEMPLATE = SEC_DATA_BASE_URL + "/submissions/CIK{cik_10}.json"
SEC_ARCHIVES_URL_TEMPLATE = (
    SEC_BASE_URL
    + "/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{filename}"
)

ANNUAL_FORM_TYPES = ("10-K",)
QUARTERLY_FORM_TYPES = ("10-Q",)
TARGET_FORM_TYPES = ANNUAL_FORM_TYPES + QUARTERLY_FORM_TYPES

ANNUAL_REPORTS_TO_FETCH = 5
QUARTERLY_REPORTS_TO_FETCH = 15
TARGET_CURRENCY = "USD"

# Number of most-recent fiscal years to keep per ticker in select_target_accessions.
# The database was built and verified on 6. This constant did NOT previously exist: the
# call site read `getattr(config, "FISCAL_YEARS_TO_FETCH", ANNUAL_REPORTS_TO_FETCH + 1)`,
# whose fallback (5 + 1) is also 6, so the effective value has always been 6. It is now
# defined explicitly (the old CLAUDE.md "7" was a documentation error — the constant was
# never present, so the "7" never took effect). Making it real removes the fragile fallback.
FISCAL_YEARS_TO_FETCH = 6

# --- Risk-free rate (the SINGLE definition; imported by price_target.py and K_backtest.py) ---
# CONSTANT 2.0% annualized. Source/rationale: approximately the average 3-month US Treasury
# bill yield (FRED series TB3MS, https://fred.stlouisfed.org/series/TB3MS) over the 2020-2026
# sample period, rounded to a clean 2%. The 3-month T-bill is the standard academic risk-free
# proxy. A constant (not a time-varying series) is a stated simplification.
#
# FREQUENCY CONVERSION — the rate is quoted ANNUALIZED and must be converted to the horizon of
# each Sharpe calculation. Both consumers annualize ARITHMETICALLY (mean * periods_per_year over
# std * sqrt(periods_per_year)), so the per-period rf is the SIMPLE division rf/periods_per_year,
# NOT the geometric (1+rf)**(1/periods_per_year) - 1. Consistency with the annualization
# convention is what makes `(ann_return - rf) / ann_vol` come out exactly right:
#   Sharpe = mean_d/std_d*sqrt(252) = (252*mean_d)/(std_d*sqrt(252)) = ann_return/ann_vol
# so subtracting rf/252 from each daily return yields ann_return - rf in the numerator.
# NEVER subtract the annual 2% from a daily or 63-day return directly.
RISK_FREE_RATE_ANNUAL = 0.02
TRADING_DAYS_PER_YEAR = 252


def risk_free_per_period(periods_per_year: float) -> float:
    """Frequency-convert RISK_FREE_RATE_ANNUAL to a per-period rate (simple/arithmetic).

    periods_per_year=252 -> daily rf (the target's convention).
    periods_per_year=252/63 -> per-63-day-rebalance rf (the backtest's convention).
    """
    return RISK_FREE_RATE_ANNUAL / periods_per_year

COMPANIES = {
    'AAPL': '0000320193',
    'ABBV': '0001551152',
    'ABT': '0000001800',
    'ACN': '0001467373',
    'AMAT': '0000006951',
    'AMD': '0000002488',
    'AMGN': '0000318154',
    'AMZN': '0001018724',
    'APH': '0000820313',
    'APP': '0001751008',
    'AVGO': '0001730168',
    'AXP': '0000004962',
    'BA': '0000012927',
    'BAC': '0000070858',
    'BKNG': '0001075531',
    'BLK': '0002012383',
    'BRK-B': '0001067983',
    'C': '0000831001',
    'CAT': '0000018230',
    'COST': '0000909832',
    'CRM': '0001108524',
    'CSCO': '0000858877',
    'CVX': '0000093410',
    'DIS': '0001744489',
    'GE': '0000040545',
    'GEV': '0001996810',
    'GOOGL': '0001652044',
    'GS': '0000886982',
    'HD': '0000354950',
    'IBM': '0000051143',
    'INTC': '0000050863',
    'INTU': '0000896878',
    'ISRG': '0001035267',
    'JNJ': '0000200406',
    'JPM': '0000019617',
    'KLAC': '0000319201',
    'KO': '0000021344',
    'LIN': '0001707925',
    'LLY': '0000059478',
    'LRCX': '0000707549',
    'MA': '0001141391',
    'MCD': '0000063908',
    'META': '0001326801',
    'MRK': '0000310158',
    'MS': '0000895421',
    'MSFT': '0000789019',
    'MU': '0000723125',
    'NEE': '0000753308',
    'NFLX': '0001065280',
    'NOW': '0001373715',
    'NVDA': '0001045810',
    'ORCL': '0001341439',
    'PEP': '0000077476',
    'PG': '0000080424',
    'PLTR': '0001321655',
    'PM': '0001413329',
    'QCOM': '0000804328',
    'RTX': '0000101829',
    'SCHW': '0000316709',
    'SPGI': '0000064040',
    'T': '0000732717',
    'TJX': '0000109198',
    'TMO': '0000097745',
    'TSLA': '0001318605',
    'TXN': '0000097476',
    'UBER': '0001543151',
    'UNH': '0000731766',
    'V': '0001403161',
    'VZ': '0000732712',
    'WFC': '0000072971',
    'WMT': '0000104169',
    'XOM': '0000034088'
}

ADDITIONAL_CIKS_BY_TICKER = {
    'BLK': (
        '0001364742',
    ),
}

COMPANY_NAMES = {
    'AAPL': 'Apple Inc.',
    'ABBV': 'AbbVie Inc.',
    'ABT': 'Abbott Laboratories',
    'ACN': 'Accenture plc',
    'AMAT': 'Applied Materials, Inc.',
    'AMD': 'Advanced Micro Devices, Inc.',
    'AMGN': 'Amgen Inc.',
    'AMZN': 'Amazon.com, Inc.',
    'APH': 'Amphenol Corporation',
    'APP': 'AppLovin Corporation',
    'AVGO': 'Broadcom Inc.',
    'AXP': 'American Express Co.',
    'BA': 'The Boeing Company',
    'BAC': 'Bank of America Corporation',
    'BKNG': 'Booking Holdings Inc.',
    'BLK': 'BlackRock, Inc.',
    'BRK-B': 'Berkshire Hathaway Inc.',
    'C': 'Citigroup Inc.',
    'CAT': 'Caterpillar Inc.',
    'COST': 'Costco Wholesale Corporation',
    'CRM': 'Salesforce, Inc.',
    'CSCO': 'Cisco Systems, Inc.',
    'CVX': 'Chevron Corporation',
    'DIS': 'The Walt Disney Company',
    'GE': 'GE Aerospace',
    'GEV': 'GE Vernova Inc.',
    'GOOGL': 'Alphabet Inc. Class A',
    'GS': 'The Goldman Sachs Group, Inc.',
    'HD': 'The Home Depot, Inc.',
    'IBM': 'International Business Machines Corporation',
    'INTC': 'Intel Corporation',
    'INTU': 'Intuit Inc.',
    'ISRG': 'Intuitive Surgical, Inc.',
    'JNJ': 'Johnson & Johnson',
    'JPM': 'JPMorgan Chase & Co.',
    'KLAC': 'KLA Corporation',
    'KO': 'The Coca-Cola Company',
    'LIN': 'Linde plc',
    'LLY': 'Eli Lilly and Company',
    'LRCX': 'Lam Research Corporation',
    'MA': 'Mastercard Incorporated',
    'MCD': "McDonald's Corporation",
    'META': 'Meta Platforms, Inc.',
    'MRK': 'Merck & Co., Inc.',
    'MS': 'Morgan Stanley',
    'MSFT': 'Microsoft Corporation',
    'MU': 'Micron Technology, Inc.',
    'NEE': 'NextEra Energy, Inc.',
    'NFLX': 'Netflix, Inc.',
    'NOW': 'ServiceNow, Inc.',
    'NVDA': 'NVIDIA Corporation',
    'ORCL': 'Oracle Corporation',
    'PEP': 'PepsiCo, Inc.',
    'PG': 'The Procter & Gamble Company',
    'PLTR': 'Palantir Technologies Inc.',
    'PM': 'Philip Morris International Inc.',
    'QCOM': 'QUALCOMM Incorporated',
    'RTX': 'RTX Corporation',
    'SCHW': 'The Charles Schwab Corporation',
    'SPGI': 'S&P Global Inc.',
    'T': 'AT&T Inc.',
    'TJX': 'The TJX Companies, Inc.',
    'TMO': 'Thermo Fisher Scientific Inc.',
    'TSLA': 'Tesla, Inc.',
    'TXN': 'Texas Instruments Incorporated',
    'UBER': 'Uber Technologies, Inc.',
    'UNH': 'UnitedHealth Group Incorporated',
    'V': 'Visa Inc.',
    'VZ': 'Verizon Communications Inc.',
    'WFC': 'Wells Fargo & Company',
    'WMT': 'Walmart Inc.',
    'XOM': 'Exxon Mobil Corporation'
}


VALID_SECTORS = (
    'Technology',
    'Communication',
    'Consumer Discretionary',
    'Consumer Staples',
    'Healthcare',
    'Banks',
    'Financial Services',
    'Industrials',
    'Energy, Materials & Utilities'
)


SECTOR_BY_TICKER = {
    'AAPL': 'Technology',
    'ACN': 'Technology',
    'AMAT': 'Technology',
    'AMD': 'Technology',
    'APH': 'Technology',
    'APP': 'Technology',
    'AVGO': 'Technology',
    'CRM': 'Technology',
    'CSCO': 'Technology',
    'IBM': 'Technology',
    'INTC': 'Technology',
    'INTU': 'Technology',
    'KLAC': 'Technology',
    'LRCX': 'Technology',
    'MSFT': 'Technology',
    'MU': 'Technology',
    'NOW': 'Technology',
    'NVDA': 'Technology',
    'ORCL': 'Technology',
    'PLTR': 'Technology',
    'QCOM': 'Technology',
    'TXN': 'Technology',

    'DIS': 'Communication',
    'GOOGL': 'Communication',
    'META': 'Communication',
    'NFLX': 'Communication',
    'T': 'Communication',
    'VZ': 'Communication',

    'AMZN': 'Consumer Discretionary',
    'BKNG': 'Consumer Discretionary',
    'HD': 'Consumer Discretionary',
    'MCD': 'Consumer Discretionary',
    'TJX': 'Consumer Discretionary',
    'TSLA': 'Consumer Discretionary',
    'UBER': 'Consumer Discretionary',

    'COST': 'Consumer Staples',
    'KO': 'Consumer Staples',
    'PEP': 'Consumer Staples',
    'PG': 'Consumer Staples',
    'PM': 'Consumer Staples',
    'WMT': 'Consumer Staples',

    'ABBV': 'Healthcare',
    'ABT': 'Healthcare',
    'AMGN': 'Healthcare',
    'ISRG': 'Healthcare',
    'JNJ': 'Healthcare',
    'LLY': 'Healthcare',
    'MRK': 'Healthcare',
    'TMO': 'Healthcare',
    'UNH': 'Healthcare',

    'AXP': 'Banks',
    'BAC': 'Banks',
    'C': 'Banks',
    'GS': 'Banks',
    'JPM': 'Banks',
    'MS': 'Banks',
    'SCHW': 'Banks',
    'WFC': 'Banks',

    'BLK': 'Financial Services',
    'BRK-B': 'Financial Services',
    'MA': 'Financial Services',
    'SPGI': 'Financial Services',
    'V': 'Financial Services',

    'BA': 'Industrials',
    'CAT': 'Industrials',
    'GE': 'Industrials',
    'GEV': 'Industrials',
    'RTX': 'Industrials',

    'CVX': 'Energy, Materials & Utilities',
    'LIN': 'Energy, Materials & Utilities',
    'NEE': 'Energy, Materials & Utilities',
    'XOM': 'Energy, Materials & Utilities',
}

ACTIVE_SECTORS = (
    'Technology',
    'Communication',
    'Consumer Discretionary',
    'Consumer Staples',
    'Healthcare',
    'Banks',
    'Financial Services',
    'Industrials',
    'Energy, Materials & Utilities',
)

ACTIVE_TICKERS = (
    'AAPL', 
    'MSFT',
    'AMD',
    'AMAT',
    'APH',
    'AVGO',
    'CRM',
    'CSCO',
    'INTC',
    'LRCX',
    'MU',
    'NOW',
    'NVDA',
    'PLTR',
    'TXN',
    'ACN', 
    'APP', 
    'QCOM',
    'INTU',
    'IBM',
    'KLAC',
    'ORCL',
    'DIS',
    'GOOGL',
    'META',
    'NFLX',
    'T',
    'VZ',
    'AMZN',
    'BKNG',
    'HD',
    'MCD',
    'TJX',
    'TSLA',
    'UBER',
    'COST',
    'KO',
    'PEP',
    'PG',
    'PM',
    'WMT',
    'ABBV',
    'ABT',
    'AMGN',
    'ISRG',
    'JNJ',
    'LLY',
    'MRK',
    'TMO',
    'UNH',
    'BA',
    'CAT',
    'GE',
    'GEV',
    'RTX',
    'CVX',
    'LIN',
    'XOM',
    'NEE',
    'BLK',
    'BRK-B',
    'MA',
    'SPGI',
    'V',
    'AXP',
    'BAC',
    'C',
    'GS',
    'JPM',
    'MS',
    'SCHW',
    'WFC',
)


COMPANY_GROUPS = {
    'TechA': (
        'AAPL', 
        'MSFT'
    ),
    'TechB': (
        'AMD',
        'AMAT',
        'APH',
        'AVGO',
        'CRM',
        'CSCO',
        'INTC',
        'LRCX',
        'MU',
        'NOW',
        'NVDA',
        'PLTR',
        'TXN'
    ),
    'TechC': (
        'ACN', 
        'APP', 
        'QCOM'
    ),
    'TechD': (
        'INTU',
        'IBM',
        'KLAC',
        'ORCL'
    ),
    'CommA': (
        'DIS',
        'GOOGL',
        'META',
        'NFLX',
        'T',
        'VZ'
    ),
    'DiscA': (
       'AMZN',
        'BKNG',
        'HD',
        'MCD',
        'TJX',
        'TSLA',
        'UBER',
    ),
    'StapA': (
       'COST',
        'KO',
        'PEP',
        'PG',
        'PM',
        'WMT',
    ),
    'HealthA': (
        'ABBV',
        'ABT',
        'AMGN',
        'ISRG',
        'JNJ',
        'LLY',
        'MRK',
        'TMO',
        'UNH',
    ),
    'IndA':(
        'BA',
        'CAT',
        'GE',
        'GEV',
        'RTX',
    ),
    'EnergyA':(
        'CVX',
        'LIN',
        'XOM',
    ),
    'EnergyB':(
        'NEE',
    ),
    'FinA':(
        'BLK',
        'BRK-B',
        'MA',
        'SPGI',
        'V',
    ),
    'BankA':(
        'AXP',
        'BAC',
        'C',
        'GS',
        'JPM',
        'MS',
        'SCHW',
        'WFC',
    ),
}

DECUMULATE_YTD_TICKERS = frozenset({
    "AXP", 
    "BAC",
    "BLK",
    "BRK-B",
    "C",
    "CVX", 
    "GS", 
    "JPM",
    "LIN",
    "MA", 
    "MS",
    "NEE", 
    "SCHW",
    "SPGI",
    "V", 
    "WFC",
    "XOM",
})

def _build_company_group_index() -> tuple[dict[str, str], dict[str, list[str]]]:
    group_by_ticker: dict[str, str] = {}
    duplicate_groups: dict[str, list[str]] = {}

    for group_name, tickers in COMPANY_GROUPS.items():
        for ticker in tickers:
            if ticker in group_by_ticker:
                duplicate_groups.setdefault(ticker, [group_by_ticker[ticker]]).append(group_name)
            else:
                group_by_ticker[ticker] = group_name

    return group_by_ticker, duplicate_groups


COMPANY_GROUP_BY_TICKER, DUPLICATE_COMPANY_GROUPS = _build_company_group_index()


def cik_10(cik: str) -> str:
    return str(cik).strip().zfill(10)


def cik_int(cik: str) -> str:
    return str(int(str(cik).strip()))


def accession_no_dashes(accession_number: str) -> str:
    return accession_number.replace("-", "")


def get_company_name(ticker: str) -> str:
    return COMPANY_NAMES.get(ticker, ticker)


def get_cik(ticker: str) -> str:
    if ticker not in COMPANIES:
        raise KeyError(f"Ticker is not configured as a US SEC company: {ticker}")
    return cik_10(COMPANIES[ticker])

def get_ciks(ticker: str) -> tuple[str, ...]:
    """Return all CIKs that should be searched for a ticker.

    The first CIK is the current/main CIK. Additional CIKs are legacy CIKs.
    """
    return (
        get_cik(ticker),
        *tuple(cik_10(cik) for cik in ADDITIONAL_CIKS_BY_TICKER.get(ticker, ())),
    )

def get_company_group(ticker: str) -> str:
    if ticker in DUPLICATE_COMPANY_GROUPS:
        raise ValueError(
            f"Ticker appears in multiple accounting groups: "
            f"{ticker} -> {DUPLICATE_COMPANY_GROUPS[ticker]}"
        )

    try:
        return COMPANY_GROUP_BY_TICKER[ticker]
    except KeyError as exc:
        raise KeyError(f"Ticker is missing accounting group: {ticker}") from exc


def get_sector(ticker: str) -> str:
    try:
        return SECTOR_BY_TICKER[ticker]
    except KeyError as exc:
        raise KeyError(f"Ticker is missing project sector mapping: {ticker}") from exc


def get_tickers_for_sector(sector: str) -> list[str]:
    if sector not in ACTIVE_SECTORS:
        raise ValueError(f"Sector is not active yet: {sector}. Active sectors: {ACTIVE_SECTORS}")

    return sorted(
        ticker
        for ticker in ACTIVE_TICKERS
        if SECTOR_BY_TICKER.get(ticker) == sector
    )


def get_financial_positions_for_group(company_group: str) -> dict[str, tuple[str, ...]]:
    if company_group not in FINANCIAL_POSITIONS_BY_GROUP:
        raise ValueError(f"Unknown company group: {company_group}")

    return {
        statement_type: tuple(positions)
        for statement_type, positions in FINANCIAL_POSITIONS_BY_GROUP[company_group].items()
    }


def get_financial_positions_for_ticker(ticker: str) -> dict[str, tuple[str, ...]]:
    return get_financial_positions_for_group(get_company_group(ticker))


def get_flat_financial_positions_for_group(company_group: str) -> tuple[str, ...]:
    grouped_positions = get_financial_positions_for_group(company_group).values()
    return tuple(dict.fromkeys(position for positions in grouped_positions for position in positions))


def get_flat_financial_positions_for_ticker(ticker: str) -> tuple[str, ...]:
    return get_flat_financial_positions_for_group(get_company_group(ticker))


def get_financial_items_for_ticker(ticker: str) -> dict[str, tuple[str, ...]]:
    company_group = get_company_group(ticker)
    try:
        return FINANCIAL_ITEMS_BY_GROUP[company_group]
    except KeyError as exc:
        raise KeyError(
            f"No financial item mapping found for ticker {ticker} "
            f"in company group {company_group}"
        ) from exc


def get_concepts_for_financial_position(ticker: str, position: str) -> tuple[str, ...]:
    """Return group-specific SEC concept candidates for a financial position."""
    return tuple(get_financial_items_for_ticker(ticker).get(position, ()))


def get_inline_financial_items_for_ticker(ticker: str) -> dict:
    return INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})


def get_calculated_financial_items_for_ticker(ticker: str) -> dict:
    company_group = get_company_group(ticker)
    return {
        **CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {}),
        **CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}),
    }


def get_all_company_tickers() -> list[str]:
    return sorted(ACTIVE_TICKERS)


def validate_config() -> None:
    missing_names = sorted(set(COMPANIES) - set(COMPANY_NAMES))
    if missing_names:
        raise ValueError(f"Companies missing display names: {missing_names}")

    missing_sectors = sorted(set(COMPANIES) - set(SECTOR_BY_TICKER))
    if missing_sectors:
        raise ValueError(f"Companies missing project sectors: {missing_sectors}")

    unknown_sector_tickers = sorted(set(SECTOR_BY_TICKER) - set(COMPANIES))
    if unknown_sector_tickers:
        raise ValueError(f"Sector mapping contains unknown tickers: {unknown_sector_tickers}")

    invalid_sectors = sorted(set(SECTOR_BY_TICKER.values()) - set(VALID_SECTORS))
    if invalid_sectors:
        raise ValueError(f"Invalid sector names: {invalid_sectors}")

    invalid_active_sectors = sorted(set(ACTIVE_SECTORS) - set(VALID_SECTORS))
    if invalid_active_sectors:
        raise ValueError(f"Active sectors are not valid sectors: {invalid_active_sectors}")

    invalid_active_tickers = sorted(set(ACTIVE_TICKERS) - set(COMPANIES))
    if invalid_active_tickers:
        raise ValueError(f"Active tickers are not configured companies: {invalid_active_tickers}")

    active_tickers_wrong_sector = sorted(
        ticker for ticker in ACTIVE_TICKERS if SECTOR_BY_TICKER.get(ticker) not in ACTIVE_SECTORS
    )
    if active_tickers_wrong_sector:
        raise ValueError(f"Active tickers mapped to inactive sectors: {active_tickers_wrong_sector}")

    grouped_tickers = set(COMPANY_GROUP_BY_TICKER)
    unknown_group_tickers = sorted(grouped_tickers - set(COMPANIES))
    if unknown_group_tickers:
        raise ValueError(f"Accounting groups contain unknown tickers: {unknown_group_tickers}")

    active_tickers_missing_groups = sorted(set(ACTIVE_TICKERS) - grouped_tickers)
    if active_tickers_missing_groups:
        raise ValueError(f"Active tickers missing accounting groups: {active_tickers_missing_groups}")

    active_duplicate_groups = {
        ticker: groups
        for ticker, groups in DUPLICATE_COMPANY_GROUPS.items()
        if ticker in ACTIVE_TICKERS
    }
    if active_duplicate_groups:
        raise ValueError(
            f"Active tickers assigned to multiple accounting groups: {active_duplicate_groups}"
        )

    active_company_groups = {get_company_group(ticker) for ticker in ACTIVE_TICKERS}

    missing_position_configs = sorted(active_company_groups - set(FINANCIAL_POSITIONS_BY_GROUP))
    if missing_position_configs:
        raise ValueError(
            f"Active company groups missing financial position config: {missing_position_configs}"
        )

    missing_item_configs = sorted(active_company_groups - set(FINANCIAL_ITEMS_BY_GROUP))
    if missing_item_configs:
        raise ValueError(
            f"Active company groups missing financial item concept config: {missing_item_configs}"
        )

    _validate_positions_resolvable(active_company_groups)
    _validate_calculation_components_resolvable(active_company_groups)


def _position_has_concepts(company_group: str, position: str) -> bool:
    """Return True when a group position has explicit concept candidates."""
    return bool(FINANCIAL_ITEMS_BY_GROUP.get(company_group, {}).get(position, ()))


def _validate_positions_resolvable(active_company_groups: set[str]) -> None:
    unresolvable: list[str] = []

    for company_group in sorted(active_company_groups):
        group_tickers = [
            ticker for ticker in ACTIVE_TICKERS if get_company_group(ticker) == company_group
        ]
        group_calculations = CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})

        for position in get_flat_financial_positions_for_group(company_group):
            has_concepts = _position_has_concepts(company_group, position)
            has_group_calculation = position in group_calculations
            has_ticker_calculation = any(
                position in CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})
                for ticker in group_tickers
            )
            has_inline_rule = any(
                position in INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})
                for ticker in group_tickers
            )

            if not (has_concepts or has_group_calculation or has_ticker_calculation or has_inline_rule):
                unresolvable.append(f"{company_group}:{position}")

    if unresolvable:
        raise ValueError(
            "Active positions with no concept mapping, calculation rule, or iXBRL rule: "
            f"{unresolvable}"
        )


def _component_resolvable_for_group_tickers(
    company_group: str,
    position: str,
    tickers: list[str],
) -> bool:
    if _position_has_concepts(company_group, position):
        return True
    if position in CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {}):
        return True
    if any(position in INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}) for ticker in tickers):
        return True
    if any(position in CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}) for ticker in tickers):
        return True
    return False


def _validate_calculation_components_resolvable(active_company_groups: set[str]) -> None:
    unresolvable_components: list[str] = []

    for company_group in sorted(active_company_groups):
        group_tickers = [
            ticker for ticker in ACTIVE_TICKERS if get_company_group(ticker) == company_group
        ]

        for target_position, rule in CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {}).items():
            for component_position, _weight in rule["components"]:
                if not _component_resolvable_for_group_tickers(
                    company_group=company_group,
                    position=component_position,
                    tickers=group_tickers,
                ):
                    unresolvable_components.append(
                        f"{company_group}:{target_position} <- {component_position}"
                    )

        for ticker in group_tickers:
            for target_position, rule in CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}).items():
                for component_position, _weight in rule["components"]:
                    if not _component_resolvable_for_group_tickers(
                        company_group=company_group,
                        position=component_position,
                        tickers=[ticker],
                    ):
                        unresolvable_components.append(
                            f"{ticker}:{target_position} <- {component_position}"
                        )

    if unresolvable_components:
        raise ValueError(
            "Calculated financial items reference components with no concept mapping, "
            f"calculation rule, or iXBRL rule: {unresolvable_components}"
        )


validate_config()
