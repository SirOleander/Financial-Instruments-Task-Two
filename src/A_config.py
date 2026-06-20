from datetime import date
from pathlib import Path


# =============================================================================
# Project paths
# =============================================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

SEC_RAW_DIR = RAW_DIR / "sec"
SEC_SUBMISSIONS_DIR = SEC_RAW_DIR / "submissions"
SEC_FILINGS_DIR = SEC_RAW_DIR / "filings"
SEC_IXBRL_FACTS_DIR = SEC_RAW_DIR / "ixbrl_facts"

OUTPUT_DIR = BASE_DIR / "outputs"
VALIDATION_REPORT_DIR = OUTPUT_DIR / "validation_reports"


# =============================================================================
# SEC EDGAR settings
# =============================================================================

SEC_BASE_URL = "https://www.sec.gov"
SEC_DATA_BASE_URL = "https://data.sec.gov"

# SEC requires a descriptive User-Agent. Replace with your active email if needed.
SEC_HEADERS = {
    "User-Agent": "s5421283@stud.uni-frankfurt.de"
}

SEC_SUBMISSIONS_URL_TEMPLATE = (
    SEC_DATA_BASE_URL + "/submissions/CIK{cik_10}.json"
)

SEC_ARCHIVES_URL_TEMPLATE = (
    SEC_BASE_URL + "/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{filename}"
)

# First retrieval stage: US 10-K and 10-Q only.
ANNUAL_FORM_TYPES = ("10-K",)
QUARTERLY_FORM_TYPES = ("10-Q",)

# Conservative first retrieval window.
# We can expand after we validate iXBRL availability and extraction quality.
ANNUAL_REPORTS_TO_FETCH = 5
QUARTERLY_REPORTS_TO_FETCH = 15

CURRENT_YEAR = date.today().year
TARGET_CURRENCY = "USD"


# =============================================================================
# US SEC company universe
# =============================================================================

# CIKs are stored as strings to preserve leading zeroes.
COMPANIES = {
    "AAPL": "0000320193",
    "ABBV": "0001551152",
    "ABT": "0000001800",
    "ACN": "0001467373",
    "AMAT": "0000006951",
    "AMD": "0000002488",
    "AMGN": "0000318154",
    "AMZN": "0001018724",
    "APH": "0000820313",
    "APP": "0001751008",
    "AVGO": "0001730168",
    "AXP": "0000004962",
    "BA": "0000012927",
    "BAC": "0000070858",
    "BKNG": "0001075531",
    "BLK": "0002012383",
    "BRK-B": "0001067983",
    "C": "0000831001",
    "CAT": "0000018230",
    "COST": "0000909832",
    "CRM": "0001108524",
    "CSCO": "0000858877",
    "CVX": "0000093410",
    "DIS": "0001744489",
    "GE": "0000040545",
    "GEV": "0001996810",
    "GOOG": "0001652044",
    "GOOGL": "0001652044",
    "GS": "0000886982",
    "HD": "0000354950",
    "IBM": "0000051143",
    "INTC": "0000050863",
    "INTU": "0000896878",
    "ISRG": "0001035267",
    "JNJ": "0000200406",
    "JPM": "0000019617",
    "KLAC": "0000319201",
    "KO": "0000021344",
    "LIN": "0001707925",
    "LLY": "0000059478",
    "LRCX": "0000707549",
    "MA": "0001141391",
    "MCD": "0000063908",
    "META": "0001326801",
    "MRK": "0000310158",
    "MS": "0000895421",
    "MSFT": "0000789019",
    "MU": "0000723125",
    "NEE": "0000753308",
    "NFLX": "0001065280",
    "NOW": "0001373715",
    "NVDA": "0001045810",
    "ORCL": "0001341439",
    "PEP": "0000077476",
    "PG": "0000080424",
    "PLTR": "0001321655",
    "PM": "0001413329",
    "QCOM": "0000804328",
    "RTX": "0000101829",
    "SCHW": "0000316709",
    "SPGI": "0000064040",
    "T": "0000732717",
    "TJX": "0000109198",
    "TMO": "0000097745",
    "TSLA": "0001318605",
    "TXN": "0000097476",
    "UBER": "0001543151",
    "UNH": "0000731766",
    "V": "0001403161",
    "VZ": "0000732712",
    "WFC": "0000072971",
    "WMT": "0000104169",
    "XOM": "0000034088",
}


COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "ABBV": "AbbVie Inc.",
    "ABT": "Abbott Laboratories",
    "ACN": "Accenture plc",
    "AMAT": "Applied Materials, Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
    "AMGN": "Amgen Inc.",
    "AMZN": "Amazon.com, Inc.",
    "APH": "Amphenol Corporation",
    "APP": "AppLovin Corporation",
    "AVGO": "Broadcom Inc.",
    "AXP": "American Express Co.",
    "BA": "The Boeing Company",
    "BAC": "Bank of America Corporation",
    "BKNG": "Booking Holdings Inc.",
    "BLK": "BlackRock, Inc.",
    "BRK-B": "Berkshire Hathaway Inc.",
    "C": "Citigroup Inc.",
    "CAT": "Caterpillar Inc.",
    "COST": "Costco Wholesale Corporation",
    "CRM": "Salesforce, Inc.",
    "CSCO": "Cisco Systems, Inc.",
    "CVX": "Chevron Corporation",
    "DIS": "The Walt Disney Company",
    "GE": "GE Aerospace",
    "GEV": "GE Vernova Inc.",
    "GOOG": "Alphabet Inc. Class C",
    "GOOGL": "Alphabet Inc. Class A",
    "GS": "The Goldman Sachs Group, Inc.",
    "HD": "The Home Depot, Inc.",
    "IBM": "International Business Machines Corporation",
    "INTC": "Intel Corporation",
    "INTU": "Intuit Inc.",
    "ISRG": "Intuitive Surgical, Inc.",
    "JNJ": "Johnson & Johnson",
    "JPM": "JPMorgan Chase & Co.",
    "KLAC": "KLA Corporation",
    "KO": "The Coca-Cola Company",
    "LIN": "Linde plc",
    "LLY": "Eli Lilly and Company",
    "LRCX": "Lam Research Corporation",
    "MA": "Mastercard Incorporated",
    "MCD": "McDonald's Corporation",
    "META": "Meta Platforms, Inc.",
    "MRK": "Merck & Co., Inc.",
    "MS": "Morgan Stanley",
    "MSFT": "Microsoft Corporation",
    "MU": "Micron Technology, Inc.",
    "NEE": "NextEra Energy, Inc.",
    "NFLX": "Netflix, Inc.",
    "NOW": "ServiceNow, Inc.",
    "NVDA": "NVIDIA Corporation",
    "ORCL": "Oracle Corporation",
    "PEP": "PepsiCo, Inc.",
    "PG": "The Procter & Gamble Company",
    "PLTR": "Palantir Technologies Inc.",
    "PM": "Philip Morris International Inc.",
    "QCOM": "QUALCOMM Incorporated",
    "RTX": "RTX Corporation",
    "SCHW": "The Charles Schwab Corporation",
    "SPGI": "S&P Global Inc.",
    "T": "AT&T Inc.",
    "TJX": "The TJX Companies, Inc.",
    "TMO": "Thermo Fisher Scientific Inc.",
    "TSLA": "Tesla, Inc.",
    "TXN": "Texas Instruments Incorporated",
    "UBER": "Uber Technologies, Inc.",
    "UNH": "UnitedHealth Group Incorporated",
    "V": "Visa Inc.",
    "VZ": "Verizon Communications Inc.",
    "WFC": "Wells Fargo & Company",
    "WMT": "Walmart Inc.",
    "XOM": "Exxon Mobil Corporation",
}


# =============================================================================
# Project sector mapping for US companies only
# =============================================================================

VALID_SECTORS = (
    "Technology",
    "Communication",
    "Consumer Discretionary",
    "Consumer Staples",
    "Healthcare",
    "Banks",
    "Financial Services",
    "Industrials",
    "Energy, Materials & Utilities",
)

SECTOR_BY_TICKER = {
    # Technology
    "AAPL": "Technology",
    "ACN": "Technology",
    "AMAT": "Technology",
    "AMD": "Technology",
    "APH": "Technology",
    "APP": "Technology",
    "AVGO": "Technology",
    "CRM": "Technology",
    "CSCO": "Technology",
    "IBM": "Technology",
    "INTC": "Technology",
    "INTU": "Technology",
    "KLAC": "Technology",
    "LRCX": "Technology",
    "MSFT": "Technology",
    "MU": "Technology",
    "NOW": "Technology",
    "NVDA": "Technology",
    "ORCL": "Technology",
    "PLTR": "Technology",
    "QCOM": "Technology",
    "TXN": "Technology",

    # Communication
    "DIS": "Communication",
    "GOOG": "Communication",
    "GOOGL": "Communication",
    "META": "Communication",
    "NFLX": "Communication",
    "T": "Communication",
    "VZ": "Communication",

    # Consumer Discretionary
    "AMZN": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "TJX": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "UBER": "Consumer Discretionary",

    # Consumer Staples
    "COST": "Consumer Staples",
    "KO": "Consumer Staples",
    "PEP": "Consumer Staples",
    "PG": "Consumer Staples",
    "PM": "Consumer Staples",
    "WMT": "Consumer Staples",

    # Healthcare
    "ABBV": "Healthcare",
    "ABT": "Healthcare",
    "AMGN": "Healthcare",
    "ISRG": "Healthcare",
    "JNJ": "Healthcare",
    "LLY": "Healthcare",
    "MRK": "Healthcare",
    "TMO": "Healthcare",
    "UNH": "Healthcare",

    # Banks
    "BAC": "Banks",
    "C": "Banks",
    "GS": "Banks",
    "JPM": "Banks",
    "MS": "Banks",
    "WFC": "Banks",

    # Financial Services
    "AXP": "Financial Services",
    "BLK": "Financial Services",
    "BRK-B": "Financial Services",
    "MA": "Financial Services",
    "SCHW": "Financial Services",
    "SPGI": "Financial Services",
    "V": "Financial Services",

    # Industrials
    "BA": "Industrials",
    "CAT": "Industrials",
    "GE": "Industrials",
    "RTX": "Industrials",

    # Energy, Materials & Utilities
    "CVX": "Energy, Materials & Utilities",
    "GEV": "Energy, Materials & Utilities",
    "LIN": "Energy, Materials & Utilities",
    "NEE": "Energy, Materials & Utilities",
    "XOM": "Energy, Materials & Utilities",
}


SECTOR_RETRIEVAL_ORDER = (
    "Technology",
)


# =============================================================================
# Active retrieval scope
# =============================================================================

# We start with Technology only. Other sectors should be added only after
# the current sector has been validated.
ACTIVE_SECTORS = (
    "Technology",
)

ACTIVE_TICKERS = (
    "AAPL",
    "ACN",
    "AMAT",
    "AMD",
    "APH",
    "APP",
    "AVGO",
    "CRM",
    "CSCO",
    "IBM",
    "INTC",
    "INTU",
    "KLAC",
    "LRCX",
    "MSFT",
    "MU",
    "NOW",
    "NVDA",
    "ORCL",
    "PLTR",
    "QCOM",
    "TXN",

)



# =============================================================================
# Accounting presentation groups
# =============================================================================

# These groups are for financial-statement extraction logic only.
# They are not the same as the project sector groups above.

COMPANY_GROUPS = {
    "TechA": (
        "AAPL",
        "MSFT",
    ),
    "TechB": (
        "AMD",
        "AMAT",
        "APH",
        "AVGO",
        "CRM",
        "CSCO",
        "INTC",
        "LRCX",
        "MU",
        "NOW",
        "NVDA",
        "PLTR",
        "TXN",
    ),
    "TechC": (
        "ACN",   # No clean gross profit in standard companyfacts form
        "APP",   # No gross profit
        "QCOM",  # No gross profit
    ),
    "TechD": (
        "INTU",
        "IBM",   # No clean operating income; do not calculate generically
        "KLAC",
        "ORCL",  # ORCL-specific cost-of-revenue components via iXBRL
    ),

}


# =============================================================================
# Group-specific financial positions needed for retrieval
# =============================================================================

# This is the main retrieval target layer for the current project stage.
#
# It defines WHAT financial positions should be retrieved for each accounting
# group. It does not define HOW to retrieve each concept. The "how" is handled by:
# - FINANCIAL_ITEMS_BY_GROUP            (companyfacts US-GAAP concept candidates)
# - INLINE_FINANCIAL_ITEMS_BY_TICKER    (targeted iXBRL fallback rules)
# - CALCULATED_FINANCIAL_ITEMS_BY_GROUP (group-level calculated positions)
# - CALCULATED_FINANCIAL_ITEMS_BY_TICKER(ticker-level calculated positions)
#
# Every position listed here for an ACTIVE group must be resolvable by at least
# one of those mechanisms. validate_config() enforces this at import time.
#
# Keep this layer strict:
# - no revenue breakdowns
# - no product/service/segment revenues
# - no non-financial operating KPIs
# - no stock data
# - no strategic/non-financial data

FINANCIAL_POSITIONS_BY_GROUP = {
    "TechA": {
        "income_statement": (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "research_and_development",
            "operating_income",
            "income_before_tax",
            "income_tax",
            "net_income",
        ),
        "balance_sheet": (
            "cash_and_cash_equivalents",
            "total_assets",
            "total_equity",
            "commercial_paper",
            "long_term_debt_current",
            "short_term_debt",
            "long_term_debt",
        ),
        "cash_flow_statement": (
            "operating_cash_flow",
            "capital_expenditure",
        ),
    },

    "TechB": {
        "income_statement": (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "research_and_development",
            "operating_income",
            "income_before_tax",
            "income_tax",
            "net_income",
        ),
        "balance_sheet": (
            "cash_and_cash_equivalents",
            "total_assets",
            "total_equity",
            "short_term_debt",
            "long_term_debt",
        ),
        "cash_flow_statement": (
            "operating_cash_flow",
            "capital_expenditure",
        ),
    },

    "TechC": {
        "income_statement": (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "research_and_development",
            "operating_income",
            "income_before_tax",
            "income_tax",
            "net_income",
        ),
        "balance_sheet": (
            "cash_and_cash_equivalents",
            "total_assets",
            "total_equity",
            "short_term_debt",
            "long_term_debt",
        ),
        "cash_flow_statement": (
            "operating_cash_flow",
            "capital_expenditure",
        ),
    },
"TechD": {
        "income_statement": (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "research_and_development",
            "operating_income",
            "income_before_tax",
            "income_tax",
            "net_income",
        ),
        "balance_sheet": (
            "cash_and_cash_equivalents",
            "total_assets",
            "total_equity",
            "short_term_debt",
            "long_term_debt",
        ),
        "cash_flow_statement": (
            "operating_cash_flow",
            "capital_expenditure",
        ),
    },
}


FINANCIAL_POSITION_SIGN_RULES = {
    "capital_expenditure": "store_positive_absolute_value",
}


def get_financial_positions_for_group(
    company_group: str,
) -> dict[str, tuple[str, ...]]:
    """Return financial positions to retrieve for a company group."""
    if company_group not in FINANCIAL_POSITIONS_BY_GROUP:
        raise ValueError(f"Unknown company group: {company_group}")

    return {
        statement_type: tuple(positions)
        for statement_type, positions in FINANCIAL_POSITIONS_BY_GROUP[company_group].items()
    }


def get_financial_positions_for_ticker(
    ticker: str,
) -> dict[str, tuple[str, ...]]:
    """Return financial positions to retrieve for a ticker's company group."""
    return get_financial_positions_for_group(
        company_group=get_company_group(ticker),
    )


def get_flat_financial_positions_for_group(
    company_group: str,
) -> tuple[str, ...]:
    """Return a flat, de-duplicated tuple of positions for a company group."""
    grouped = get_financial_positions_for_group(company_group)

    positions: list[str] = []

    for statement_positions in grouped.values():
        for position in statement_positions:
            if position not in positions:
                positions.append(position)

    return tuple(positions)


def get_flat_financial_positions_for_ticker(
    ticker: str,
) -> tuple[str, ...]:
    """Return a flat, de-duplicated tuple of positions for a ticker."""
    return get_flat_financial_positions_for_group(get_company_group(ticker))


FINANCIAL_ITEMS_BY_GROUP = {
    "TechA": {
        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
        ),
        "cost_of_revenue": (
            "CostOfGoodsAndServicesSold",
        ),
        "gross_profit": (
            "GrossProfit",
        ),
        "research_and_development": (
            "ResearchAndDevelopmentExpense",
        ),
        "operating_income": (
            "OperatingIncomeLoss",
        ),
        "income_before_tax": (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
        "income_tax": (
            "IncomeTaxExpenseBenefit",
        ),
        "net_income": (
            "NetIncomeLoss",
        ),
        "cash_and_cash_equivalents": (
            "CashAndCashEquivalentsAtCarryingValue",
        ),
        "total_assets": (
            "Assets",
        ),
        "total_equity": (
            "StockholdersEquity",
        ),
        "commercial_paper": (
            "CommercialPaper",
        ),
        "long_term_debt_current": (
            "LongTermDebtCurrent",
        ),
        "short_term_debt": (
            
        ),
        "long_term_debt": (
            "LongTermDebtNoncurrent",
        ),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
        ),
    },
    "TechB": {
        "revenue": (
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
        ),
        "cost_of_revenue": (
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        ),
        "gross_profit": (
            "GrossProfit",
        ),
        "research_and_development": (
            "ResearchAndDevelopmentExpense",
        ),
        "operating_income": (
            "OperatingIncomeLoss",
        ),
        "income_before_tax": (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
        "income_tax": (
            "IncomeTaxExpenseBenefit",
        ),
        "net_income": (
            "NetIncomeLoss",
            "ProfitLoss",
        ),
        "cash_and_cash_equivalents": (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "total_assets": (
            "Assets",
        ),
        "total_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "short_term_debt": (
            "DebtCurrent",
            "ShortTermBorrowings",
            "LongTermDebtCurrent",
            "LongTermDebtAndCapitalLeaseObligationsCurrent",
        ),
        "long_term_debt": (
            "LongTermDebtNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
            "ConvertibleLongTermNotesPayable",
        ),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
    },
    "TechC": {
        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ),
        "cost_of_revenue": (
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
        ),
        "gross_profit": (
            "GrossProfit",
        ),
        "research_and_development": (
            "ResearchAndDevelopmentExpense",
        ),
        "operating_income": (
            "OperatingIncomeLoss",
        ),
        "income_before_tax": (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        ),
        "income_tax": (
            "IncomeTaxExpenseBenefit",
        ),
        "net_income": (
            "NetIncomeLoss",
        ),
        "cash_and_cash_equivalents": (
            "CashAndCashEquivalentsAtCarryingValue",
        ),
        "total_assets": (
            "Assets",
        ),
        "total_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "short_term_debt": (
            "DebtCurrent",
            "LongTermDebtCurrent",
            "ShortTermBorrowings",
        ),
        "long_term_debt": (
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtAndCapitalLeaseObligations",
        ),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
    },
    "TechD": {
        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ),
        "cost_of_revenue": (
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
        ),
        "gross_profit": (
            "GrossProfit",
        ),
        "research_and_development": (
            "ResearchAndDevelopmentExpense",
        ),
        "operating_income": (
            "OperatingIncomeLoss",
        ),
        "income_before_tax": (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
        "income_tax": (
            "IncomeTaxExpenseBenefit",
        ),
        "net_income": (
            "NetIncomeLoss",
            "ProfitLoss",
        ),
        "cash_and_cash_equivalents": (
            "CashAndCashEquivalentsAtCarryingValue",
        ),
        "total_assets": (
            "Assets",
        ),
        "total_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "short_term_debt": (
            "LongTermDebtAndCapitalLeaseObligationsCurrent",
            "ConvertibleDebtCurrent",
            "DebtCurrent",
            "LongTermDebtCurrent",
        ),
        "long_term_debt": (
            "LongTermDebtNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        ),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capital_expenditure": (
            "PaymentsToAcquirePropertyPlantAndEquipment",
        ),
    },
}


# =============================================================================
# Ticker-specific financial statement overrides
# =============================================================================

INLINE_FINANCIAL_ITEMS_BY_TICKER = { 
    "AAPL": {
        "commercial_paper": {
            "concepts": (
                "CommercialPaper",
            ),
            "statement_type": "balance_sheet",
            "required_axis_member": {
                "ShortTermDebtTypeAxis": "CommercialPaperMember",
            },
        },
    },
    "INTU": {
    "cost_of_product": {
        "concepts": (
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        ),
        "statement_type": "income_statement",
        "required_axis_member": {
            "ProductOrServiceAxis": (
                "ProductMember",
                "ProductAndOtherMember",
            ),
        },
    },
    "cost_of_service": {
        "concepts": (
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        ),
        "statement_type": "income_statement",
        "required_axis_member": {
            "ProductOrServiceAxis": (
                "ServiceMember",
                "ServicesMember",
            ),
        },
    },
    "cost_of_amo": {
        "concepts": (
            "CostOfGoodsAndServicesSoldAmortization",
        ),
        "statement_type": "income_statement",
    },
},
    "LRCX": {
        "cost_of_revenue":{
            "concepts": (
                "CostOfGoodsAndServicesSoldExcludingRestructuringCharges",
            ),
            "statement_type": "income_statement",
        },
    },
    "NVDA": {
        "capital_expenditure":{
            "concepts":(
                "PurchasesOfPropertyAndEquipmentAndIntangibleAssets",
            ),
            "statement_type": "cash_flow_statement",
        },
    },
    "ORCL": {
        "cloud_services_and_license_support_cost": {
            "concepts": (
                "CloudServicesAndLicenseSupportExpenses",
            ),
            "statement_type": "income_statement",
        },
        "hardware_cost": {
            "concepts": (
                "HardwareExpenses",
            ),
            "statement_type": "income_statement",
        },
        "services_cost": {
            "concepts": (
                "ServicesExpense",
            ),
            "statement_type": "income_statement",
        },
    },
}


CALCULATED_FINANCIAL_ITEMS_BY_GROUP = {
    "TechA": {
        "short_term_debt": {
            "concept": "calc_short_term_debt",
            "components": (
                ("commercial_paper", 1),
                ("long_term_debt_current", 1),
            ),
            "missing_components_as_zero": True,
            "require_at_least_one_component": True,
            "overwrite_existing": True,
        },
    },
    "TechC": {
        "gross_profit": {
            "concept": "calc_gross_profit",
            "components": (
                ("revenue", 1),
                ("cost_of_revenue", -1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
        },
    },
    "TechD": {
        "gross_profit": {
            "concept": "calc_gross_profit",
            "components": (
                ("revenue", 1),
                ("cost_of_revenue", -1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
        },
    },
}


CALCULATED_FINANCIAL_ITEMS_BY_TICKER = {
    "INTU": {
        "cost_of_revenue": {
            "concept": "calc_cost_of_revenue",
            "components": (
                ("cost_of_service", 1),
                ("cost_of_product", 1),
                ("cost_of_amo", 1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
            "quality": "company_specific_calculation",
        },
        "gross_profit": {
            "concept": "calc_gross_profit",
            "components": (
                ("revenue", 1),
                ("cost_of_revenue", -1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
        },
    },
    "ORCL": {
        # ORCL does not report a single cost_of_revenue line. It is rebuilt from
        # company-specific iXBRL component costs. The calculator runs in
        # multiple passes, so gross_profit can then use this result.
        "cost_of_revenue": {
            "concept": "calc_orcl_cost_of_revenue",
            "components": (
                ("cloud_services_and_license_support_cost", 1),
                ("hardware_cost", 1),
                ("services_cost", 1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
            "quality": "company_specific_calculation",
        },
        "gross_profit": {
            "concept": "calc_gross_profit",
            "components": (
                ("revenue", 1),
                ("cost_of_revenue", -1),
            ),
            "missing_components_as_zero": False,
            "require_at_least_one_component": False,
            "overwrite_existing": False,
        },
    },
}


FINANCIAL_ITEM_ORDER_BY_GROUP = {}

# =============================================================================
# Shared fallback concept candidates
# =============================================================================

# This mapping complements FINANCIAL_ITEMS_BY_GROUP. It is used by
# get_concepts_for_financial_position() ONLY when a position is not defined in
# the ticker's group-level item mapping. It provides generic balance sheet,
# cash flow, and (for future non-Technology groups) bank/regulatory concept
# candidates so new groups can be added without redefining every concept.

FINANCIAL_POSITION_CONCEPTS = {
    "cash_and_cash_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "total_assets": ("Assets",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "total_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "PartnersCapital",
    ),
    "short_term_debt": (
        "ShortTermBorrowings",
        "ShortTermDebt",
        "ShortTermDebtCurrent",
    ),
    "long_term_debt": (
        "LongTermDebt",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligations",
    ),
    "inventory": (
        "InventoryNet",
        "InventoryFinishedGoodsNetOfReserves",
    ),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "depreciation_and_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ),
    "total_loans": (
        "LoansAndLeasesReceivableNetReportedAmount",
        "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
    ),
    "total_deposits": ("Deposits",),
    "average_earning_assets": (),
    "nonperforming_loans": (),
    "cet1_ratio": (),
    "tier1_capital_ratio": (),
    "leverage_ratio": (),
}


def get_concepts_for_financial_position(
    ticker: str,
    position: str,
) -> tuple[str, ...]:
    """
    Return concept candidates for a standardized financial position.

    Priority:
    1. ticker/group-specific financial item mappings
    2. additional financial position concept mappings
    3. empty tuple if the item needs manual/iXBRL discovery
    """
    ticker_items = get_financial_items_for_ticker(ticker)

    if position in ticker_items:
        return tuple(ticker_items[position])

    return tuple(FINANCIAL_POSITION_CONCEPTS.get(position, ()))


# =============================================================================
# Helper functions
# =============================================================================

def cik_10(cik: str) -> str:
    """Return SEC CIK as a 10-digit zero-padded string."""
    return str(cik).strip().zfill(10)


def cik_int(cik: str) -> str:
    """Return SEC CIK without leading zeroes for SEC archive URLs."""
    return str(int(str(cik).strip()))


def accession_no_dashes(accession_number: str) -> str:
    """Return accession number without dashes for SEC archive URLs."""
    return accession_number.replace("-", "")


def get_company_name(ticker: str) -> str:
    """Return company display name."""
    return COMPANY_NAMES.get(ticker, ticker)


def get_cik(ticker: str) -> str:
    """Return 10-digit SEC CIK for a configured US company."""
    if ticker not in COMPANIES:
        raise KeyError(f"Ticker is not configured as a US SEC company: {ticker}")

    return cik_10(COMPANIES[ticker])


def get_company_group(ticker: str) -> str:
    """Return accounting presentation group for a ticker.

    The project now uses explicit group-based retrieval only.
    Therefore every active ticker must appear in exactly one company group.
    """
    matching_groups = [
        group_name
        for group_name, tickers in COMPANY_GROUPS.items()
        if ticker in tickers
    ]

    if not matching_groups:
        raise KeyError(f"Ticker is missing accounting group: {ticker}")

    if len(matching_groups) > 1:
        raise ValueError(
            f"Ticker appears in multiple accounting groups: {ticker} -> {matching_groups}"
        )

    return matching_groups[0]


def get_sector(ticker: str) -> str:
    """Return project sector for a ticker."""
    if ticker not in SECTOR_BY_TICKER:
        raise KeyError(f"Ticker is missing project sector mapping: {ticker}")

    return SECTOR_BY_TICKER[ticker]


def get_tickers_for_sector(sector: str) -> list[str]:
    """Return active configured US SEC tickers in a project sector."""
    if sector not in ACTIVE_SECTORS:
        raise ValueError(
            f"Sector is not active yet: {sector}. "
            f"Active sectors: {ACTIVE_SECTORS}"
        )

    return sorted(
        ticker for ticker, mapped_sector in SECTOR_BY_TICKER.items()
        if mapped_sector == sector and ticker in ACTIVE_TICKERS
    )


def get_financial_items_for_ticker(ticker: str) -> dict[str, tuple[str, ...]]:
    """Return financial statement concept candidates for a ticker."""
    company_group = get_company_group(ticker)

    if company_group in FINANCIAL_ITEMS_BY_GROUP:
        return FINANCIAL_ITEMS_BY_GROUP[company_group]

    raise KeyError(
        f"No financial item mapping found for ticker {ticker} "
        f"in company group {company_group}"
    )


def get_inline_financial_items_for_ticker(ticker: str) -> dict:
    """Return ticker-specific inline XBRL extraction rules."""
    return INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})


def get_calculated_financial_items_for_ticker(ticker: str) -> dict:
    """Return group-level and ticker-specific calculated financial item rules."""
    company_group = get_company_group(ticker)

    rules = {}

    group_rules = CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})
    ticker_rules = CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})

    rules.update(group_rules)
    rules.update(ticker_rules)

    return rules


def get_financial_item_display_order(
    item_key: str,
    ticker: str | None = None,
    company_group: str | None = None,
) -> int:
    """Return display/output order for a financial statement item."""
    if company_group is None:
        if ticker is None:
            return 999
        company_group = get_company_group(ticker)

    return FINANCIAL_ITEM_ORDER_BY_GROUP.get(company_group, {}).get(item_key, 999)


def get_all_company_tickers() -> list[str]:
    """Return active configured US SEC company tickers."""
    return sorted(ACTIVE_TICKERS)


def validate_config() -> None:
    """Run basic config consistency checks for the current active universe."""
    missing_names = sorted(set(COMPANIES) - set(COMPANY_NAMES))
    if missing_names:
        raise ValueError(f"Companies missing display names: {missing_names}")

    missing_sectors = sorted(set(COMPANIES) - set(SECTOR_BY_TICKER))
    if missing_sectors:
        raise ValueError(f"Companies missing project sectors: {missing_sectors}")

    unknown_sector_tickers = sorted(set(SECTOR_BY_TICKER) - set(COMPANIES))
    if unknown_sector_tickers:
        raise ValueError(
            f"Sector mapping contains non-US or unknown tickers: {unknown_sector_tickers}"
        )

    invalid_sectors = sorted(set(SECTOR_BY_TICKER.values()) - set(VALID_SECTORS))
    if invalid_sectors:
        raise ValueError(f"Invalid sector names: {invalid_sectors}")

    inactive_active_sectors = sorted(set(ACTIVE_SECTORS) - set(VALID_SECTORS))
    if inactive_active_sectors:
        raise ValueError(f"Active sectors are not valid sectors: {inactive_active_sectors}")

    inactive_active_tickers = sorted(set(ACTIVE_TICKERS) - set(COMPANIES))
    if inactive_active_tickers:
        raise ValueError(f"Active tickers are not configured companies: {inactive_active_tickers}")

    active_tickers_wrong_sector = sorted(
        ticker
        for ticker in ACTIVE_TICKERS
        if SECTOR_BY_TICKER.get(ticker) not in ACTIVE_SECTORS
    )
    if active_tickers_wrong_sector:
        raise ValueError(
            f"Active tickers mapped to inactive sectors: {active_tickers_wrong_sector}"
        )

    grouped_tickers = {
        ticker
        for tickers in COMPANY_GROUPS.values()
        for ticker in tickers
    }

    unknown_group_tickers = sorted(grouped_tickers - set(COMPANIES))
    if unknown_group_tickers:
        raise ValueError(
            f"Accounting groups contain non-US or unknown tickers: {unknown_group_tickers}"
        )

    # Only active tickers must have accounting groups during the current retrieval stage.
    # This lets you add future sector/company groups gradually.
    active_tickers_missing_groups = sorted(set(ACTIVE_TICKERS) - grouped_tickers)
    if active_tickers_missing_groups:
        raise ValueError(
            f"Active tickers missing accounting groups: {active_tickers_missing_groups}"
        )

    duplicate_group_memberships = {}
    for ticker in ACTIVE_TICKERS:
        groups = [
            group_name
            for group_name, tickers in COMPANY_GROUPS.items()
            if ticker in tickers
        ]
        if len(groups) > 1:
            duplicate_group_memberships[ticker] = groups

    if duplicate_group_memberships:
        raise ValueError(
            "Active tickers assigned to multiple accounting groups: "
            f"{duplicate_group_memberships}"
        )

    active_company_groups = {
        get_company_group(ticker)
        for ticker in ACTIVE_TICKERS
    }

    missing_active_group_position_configs = sorted(
        active_company_groups - set(FINANCIAL_POSITIONS_BY_GROUP)
    )
    if missing_active_group_position_configs:
        raise ValueError(
            "Active company groups missing financial position config: "
            f"{missing_active_group_position_configs}"
        )

    missing_active_group_item_configs = sorted(
        active_company_groups - set(FINANCIAL_ITEMS_BY_GROUP)
    )
    if missing_active_group_item_configs:
        raise ValueError(
            "Active company groups missing financial item concept config: "
            f"{missing_active_group_item_configs}"
        )

    _validate_positions_resolvable(active_company_groups)
    _validate_calculation_components_resolvable(active_company_groups)


def _position_has_concepts(company_group: str, position: str) -> bool:
    """Return True if a position resolves to a non-empty concept candidate list.

    This mirrors the shadowing logic in get_concepts_for_financial_position():
    a group-level item mapping (even an empty one) hides the shared fallback.
    """
    group_items = FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})

    if position in group_items:
        return bool(group_items[position])

    return bool(FINANCIAL_POSITION_CONCEPTS.get(position))


def _validate_positions_resolvable(active_company_groups: set[str]) -> None:
    """Ensure every active position can be retrieved or calculated.

    A position is resolvable if it has at least one of:
    - a non-empty companyfacts concept candidate list,
    - a group-level or ticker-level calculation rule,
    - a ticker-level iXBRL fallback rule.

    This catches positions that would silently stay empty forever, such as a
    short_term_debt position with no concepts and no calculation rule.
    """
    unresolvable: list[str] = []

    for company_group in sorted(active_company_groups):
        group_tickers = [
            ticker
            for ticker in ACTIVE_TICKERS
            if get_company_group(ticker) == company_group
        ]
        group_calc_rules = CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})

        for position in get_flat_financial_positions_for_group(company_group):
            has_concepts = _position_has_concepts(company_group, position)
            has_group_calc = position in group_calc_rules
            has_ticker_calc = any(
                position in CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})
                for ticker in group_tickers
            )
            has_inline = any(
                position in INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})
                for ticker in group_tickers
            )

            if not (has_concepts or has_group_calc or has_ticker_calc or has_inline):
                unresolvable.append(f"{company_group}:{position}")

    if unresolvable:
        raise ValueError(
            "Active positions with no concept mapping, calculation rule, or "
            f"iXBRL rule: {unresolvable}"
        )


def _component_resolvable_for_group_tickers(
    company_group: str,
    position: str,
    tickers: list[str],
) -> bool:
    """Return True if a calculation component can be built for a group.

    Calculation components are sometimes normal output positions and sometimes
    ticker-specific iXBRL helper positions. This validation keeps both cases
    explicit and catches rules that reference components that will never be
    retrieved.
    """
    group_calc_rules = CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})

    if _position_has_concepts(company_group, position):
        return True

    if position in group_calc_rules:
        return True

    if any(position in INLINE_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}) for ticker in tickers):
        return True

    if any(position in CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {}) for ticker in tickers):
        return True

    return False


def _validate_calculation_components_resolvable(active_company_groups: set[str]) -> None:
    """Ensure every configured calculation references retrievable components."""
    unresolvable_components: list[str] = []

    for company_group in sorted(active_company_groups):
        group_tickers = [
            ticker
            for ticker in ACTIVE_TICKERS
            if get_company_group(ticker) == company_group
        ]

        group_rules = CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})
        for target_position, rule in group_rules.items():
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
            ticker_rules = CALCULATED_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})
            for target_position, rule in ticker_rules.items():
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
            "Calculated financial items reference components with no concept "
            "mapping, calculation rule, or iXBRL rule: "
            f"{unresolvable_components}"
        )


validate_config()