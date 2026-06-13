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
ANNUAL_REPORTS_TO_FETCH = 7
QUARTERLY_REPORTS_TO_FETCH = 20

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
    "TechA":(
        "AAPL",
        "AMAT",
        "AMD",
        "APH",
        "APP",
        "AVGO",
        "CRM",
        "CSCO",
        "INTC",
        "LRCX",
        "MSFT",
        "MU",
        "NOW",
        "NVDA",
        "PLTR",
        "TXN",

    ),
    "TechB":( #No Gross Profit, No Operating Income, No COGS
        "ACN", #No GP
        "APP", #No GP
        "IBM", #No OI
        "INTU", #No COGS
        "KLAC", #No GP
        "ORCL", #No COGS and GP
        "QCOM", #No GP


    ),
    "banks": (
        "AXP",
        "JPM",
        "BAC",
        "MS",
        "GS",
        "WFC",
        "C",
        "SCHW",
    ),
    "financial_services_non_bank": (
        "V",
        "MA",
        "BLK",
        "SPGI",
    ),
    "conglomerate": (
        "BRK-B",
    ),
    "managed_care": (
        "UNH",
    ),
    "utilities": (
        "NEE",
    ),
    "telecom": (
        "VZ",
        "T",
    ),
    "energy": (
        "XOM",
        "CVX",
    ),
    "special_cases": (
        "GE",
        "GEV",
    ),
    "operating_companies": (
        "AAPL",
        "ABBV",
        "ABT",
        "AMAT",
        "AMD",
        "AMGN",
        "APH",
        "AVGO",
        "CAT",
        "COST",
        "DIS",
        "HD",
        "IBM",
        "INTC",
        "ISRG",
        "JNJ",
        "KLAC",
        "KO",
        "LIN",
        "LLY",
        "LRCX",
        "MRK",
        "MU",
        "NVDA",
        "PEP",
        "PG",
        "PM",
        "QCOM",
        "RTX",
        "TJX",
        "TMO",
        "TSLA",
        "TXN",
        "WMT",
    ),
    "operating_companies_cogs": (
        "BKNG",
        "INTU",
        "MCD",
        "ORCL",
    ),
    "operating_companies_sga": (
        "ACN",
        "AMZN",
        "APP",
        "BA",
        "CRM",
        "CSCO",
        "GOOG",
        "GOOGL",
        "META",
        "MSFT",
        "NFLX",
        "NOW",
        "PLTR",
        "UBER",
    ),
}




# =============================================================================
# Sector-specific financial positions needed for KPI calculation
# =============================================================================

# This is the main retrieval target layer for the current project stage.
#
# It defines WHAT financial positions should be retrieved for each project sector.
# It does not define HOW to retrieve each concept. The "how" is still handled by:
# - FINANCIAL_ITEMS_BY_GROUP
# - INLINE_ANNUAL_FINANCIAL_ITEMS_BY_TICKER
# - CALCULATED_FINANCIAL_ITEMS_BY_GROUP
#
# Keep this layer strict:
# - no revenue breakdowns
# - no product/service/segment revenues
# - no non-financial operating KPIs
# - no stock data
# - no strategic/non-financial data

FINANCIAL_POSITIONS_BY_SECTOR = {
    "Technology": {
        "required": {
            "income_statement": (
                "revenue",
                "gross_profit",
                "operating_income",
                "income_before_tax",
                "income_tax",
                "net_income",
                "research_and_development",
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
        "conditional": {
            "income_statement": (
                "cost_of_revenue",
            ),
            "balance_sheet": (),
            "cash_flow_statement": (),
        },
    },
}


FINANCIAL_POSITION_SIGN_RULES = {
    "capital_expenditure": "store_positive_absolute_value",
}


def get_financial_positions_for_sector(
    sector: str,
    include_conditional: bool = True,
) -> dict[str, tuple[str, ...]]:
    """Return financial positions to retrieve for a sector, grouped by statement type."""
    if sector not in FINANCIAL_POSITIONS_BY_SECTOR:
        raise ValueError(f"Unknown sector: {sector}")

    sector_config = FINANCIAL_POSITIONS_BY_SECTOR[sector]
    result = {
        statement: tuple(items)
        for statement, items in sector_config["required"].items()
    }

    if include_conditional:
        for statement, items in sector_config.get("conditional", {}).items():
            existing = list(result.get(statement, ()))
            for item in items:
                if item not in existing:
                    existing.append(item)
            result[statement] = tuple(existing)

    return result


def get_financial_positions_for_ticker(
    ticker: str,
    include_conditional: bool = True,
) -> dict[str, tuple[str, ...]]:
    """Return financial positions to retrieve for a ticker's project sector."""
    return get_financial_positions_for_sector(
        sector=get_sector(ticker),
        include_conditional=include_conditional,
    )


def get_flat_financial_positions_for_sector(
    sector: str,
    include_conditional: bool = True,
) -> tuple[str, ...]:
    """Return a flat, de-duplicated tuple of financial positions for a sector."""
    grouped = get_financial_positions_for_sector(sector, include_conditional)
    positions: list[str] = []

    for items in grouped.values():
        for item in items:
            if item not in positions:
                positions.append(item)

    return tuple(positions)


def get_flat_financial_positions_for_ticker(
    ticker: str,
    include_conditional: bool = True,
) -> tuple[str, ...]:
    """Return a flat, de-duplicated tuple of financial positions for a ticker."""
    return get_flat_financial_positions_for_sector(
        sector=get_sector(ticker),
        include_conditional=include_conditional,
    )

FINANCIAL_ITEMS_BY_GROUP = {
    "TechA": {
        "revenue": (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
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
        "cash_and_cash_equivalents":(
            "CashAndCashEquivalentsAtCarryingValue",
        ),
        "total_assets":(
            "Assets",
        ),
        "total_equity":(
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "short_term_debt":(
            "ShortTermBorrowings",
            "LongTermDebtAndCapitalLeaseObligationsCurrent",
        ),
        "long_term_debt":(
            "LongTermDebtNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
        ),
        "operating_cash_flow":(
            "NetCashProvidedByUsedInOperatingActivities",
        ),
        "capital_expenditure":(
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
        "operating_expenses": (
            "OperatingExpenses",
        ),
        "sales_and_marketing": (
            "SellingAndMarketingExpense",
            "MarketingExpense",
        ),
        "research_and_development": (
            "ResearchAndDevelopmentExpense",
            "TechnologyAndDevelopmentExpense",
        ),
        "general_and_administrative": (
            "GeneralAndAdministrativeExpense",
        ),
        "operating_income": (
            "OperatingIncomeLoss",
        ),
        "nonoperating_income": (
            "NonoperatingIncomeExpense",
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
    },

}


# =============================================================================
# Ticker-specific financial statement overrides
# =============================================================================

INLINE_FINANCIAL_ITEMS_BY_TICKER = {
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
    }
}

CALCULATED_FINANCIAL_ITEMS_BY_GROUP = {
    "TechB": {
        "cost_of_revenue": {
            "concept": "calc_cost_of_revenue",
            "required_items": (
                "operating_expenses",
            ),
            "components": (
                ("operating_expenses", 1),
                ("selling_general_admin", -1),
                ("research_and_development", -1),
            ),
        },
        "gross_profit": {
            "concept": "calc_gross_profit",
            "components": (
                ("revenue", 1),
                ("cost_of_revenue", -1),
            ),
        },
        "operating_income": {
            "concept": "calc_operating_income",
            "required_items": (
                "gross_profit",
                "operating_income",
            ),
            "components": (
                ("gross_profit", 1),
                ("operating_income", -1),
            ),
        },
    }
} 

CALCULATED_FINANCIAL_ITEMS_BY_TICKER = {
    "ORCL": {
        "cost_of_revenue": {
            "concept": "CALCULATED_ORCL_REVENUE_RELATED_COSTS",
            "components": (
                ("cloud_services_and_license_support_cost", 1),
                ("hardware_cost", 1),
                ("services_cost", 1),
            ),
            "quality": "company_specific_calculation",
        },
    }
}

# =============================================================================
# Financial statement display / output order
# =============================================================================

FINANCIAL_ITEM_ORDER_BY_GROUP = {
    "operating_companies": {
        "revenue": 10,
        "cost_of_revenue": 20,
        "gross_profit": 30,
        "operating_expenses": 40,
        "research_and_development": 50,
        "selling_general_admin": 60,
        "other_operating_expenses": 70,
        "operating_income": 80,
        "nonoperating_income": 90,
        "income_before_tax": 100,
        "income_tax": 110,
        "noncontrolling_interest": 120,
        "net_income": 130,
    },
    "operating_companies_sga": {
        "revenue": 10,
        "cost_of_revenue": 20,
        "gross_profit": 30,
        "operating_expenses": 40,
        "sales_and_marketing": 50,
        "general_and_administrative": 60,
        "research_and_development": 70,
        "selling_general_admin": 80,
        "other_operating_expenses": 90,
        "operating_income": 100,
        "nonoperating_income": 110,
        "income_before_tax": 120,
        "income_tax": 130,
        "noncontrolling_interest": 140,
        "net_income": 150,
    },
    "operating_companies_cogs": {
        "revenue": 10,
        "operating_expenses": 20,
        "sales_and_marketing": 30,
        "research_and_development": 40,
        "general_and_administrative": 50,
        "selling_general_admin": 60,
        "other_operating_expenses": 70,
        "operating_income": 80,
        "nonoperating_income": 90,
        "income_before_tax": 100,
        "income_tax": 110,
        "noncontrolling_interest": 120,
        "net_income": 130,
    },
    "banks": {
        "interest_income": 10,
        "interest_expense": 20,
        "net_interest_income": 30,
        "noninterest_income": 40,
        "revenue": 50,
        "noninterest_expense": 60,
        "provision_credit_losses": 70,
        "income_before_tax": 80,
        "income_tax": 90,
        "noncontrolling_interest": 99,
        "net_income": 100,
    },
    "financial_services_non_bank": {
        "revenue": 10,
        "operating_expenses": 20,
        "operating_income": 30,
        "nonoperating_income": 40,
        "income_before_tax": 50,
        "income_tax": 60,
        "noncontrolling_interest": 66,
        "net_income": 70,
    },
    "managed_care": {
        "revenue": 10,
        "operating_expenses": 20,
        "depreciation": 30,
        "operating_income": 40,
        "income_before_tax": 50,
        "income_tax": 60,
        "net_income": 70,
    },
    "conglomerate": {
        "revenue": 10,
        "investment_gains_losses": 20,
        "operating_expenses": 30,
        "operating_income": 40,
        "nonoperating_income": 50,
        "income_before_tax": 60,
        "income_tax": 70,
        "noncontrolling_interest": 71,
        "net_income": 80,
    },
    "utilities": {
        "revenue": 10,
        "operating_expenses": 20,
        "fuel_power": 30,
        "depreciation": 40,
        "gains_disposal": 50,
        "operating_income": 60,
        "nonoperating_income": 70,
        "income_before_tax": 80,
        "income_tax": 90,
        "net_income": 100,
    },
    "telecom": {
        "revenue": 10,
        "cost_of_revenue": 20,
        "gross_profit": 30,
        "operating_expenses": 40,
        "selling_general_admin": 50,
        "depreciation": 60,
        "operating_income": 70,
        "income_before_tax": 80,
        "income_tax": 90,
        "net_income": 100,
    },
    "energy": {
        "revenue": 10,
        "operating_expenses": 20,
        "selling_general_admin": 30,
        "depreciation": 40,
        "exploration": 50,
        "income_before_tax": 60,
        "income_tax": 70,
        "net_income": 80,
    },
    "special_cases": {
        "revenue": 10,
        "cost_of_revenue": 20,
        "gross_profit": 30,
        "operating_expenses": 40,
        "selling_general_admin": 50,
        "research_and_development": 60,
        "operating_income": 70,
        "nonoperating_income": 80,
        "income_tax": 90,
        "net_income": 100,
    },
}




# =============================================================================
# Additional concept candidates for sector-position retrieval
# =============================================================================

# This mapping complements FINANCIAL_ITEMS_BY_GROUP, which mainly comes from
# income statement extraction. The sector-position layer also needs balance
# sheet, cash flow, and selected bank/regulatory items.

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
    """Return accounting presentation group for a ticker."""
    for group_name, tickers in COMPANY_GROUPS.items():
        if ticker in tickers:
            return group_name

    return "operating_companies"


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


def get_inline_annual_financial_items_for_ticker(ticker: str) -> dict:
    """Return ticker-specific annual financial-statement overrides."""
    return INLINE_ANNUAL_FINANCIAL_ITEMS_BY_TICKER.get(ticker, {})


def get_calculated_financial_items_for_ticker(ticker: str) -> dict:
    """Return calculated financial-statement item rules for a ticker."""
    company_group = get_company_group(ticker)

    return CALCULATED_FINANCIAL_ITEMS_BY_GROUP.get(company_group, {})


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
    """Run basic config consistency checks."""
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

    missing_sector_position_configs = sorted(
        set(ACTIVE_SECTORS) - set(FINANCIAL_POSITIONS_BY_SECTOR)
    )
    if missing_sector_position_configs:
        raise ValueError(
            f"Active sectors missing financial position config: {missing_sector_position_configs}"
        )

    inactive_sector_position_configs = sorted(
        set(FINANCIAL_POSITIONS_BY_SECTOR) - set(ACTIVE_SECTORS)
    )
    if inactive_sector_position_configs:
        raise ValueError(
            f"Financial position configs exist for inactive sectors: {inactive_sector_position_configs}"
        )

    grouped_tickers = {
        ticker
        for tickers in COMPANY_GROUPS.values()
        for ticker in tickers
    }
    missing_groups = sorted(set(COMPANIES) - grouped_tickers)
    if missing_groups:
        raise ValueError(f"Companies missing accounting groups: {missing_groups}")

    unknown_group_tickers = sorted(grouped_tickers - set(COMPANIES))
    if unknown_group_tickers:
        raise ValueError(
            f"Accounting groups contain non-US or unknown tickers: {unknown_group_tickers}"
        )


validate_config()
