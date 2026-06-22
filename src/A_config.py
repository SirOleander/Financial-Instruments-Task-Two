from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
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
    'GOOG': '0001652044',
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
    'GOOG': 'Alphabet Inc. Class C',
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
    'GOOG': 'Communication',
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
    'RTX': 'Industrials',

    'CVX': 'Energy, Materials & Utilities',
    'GEV': 'Energy, Materials & Utilities',
    'LIN': 'Energy, Materials & Utilities',
    'NEE': 'Energy, Materials & Utilities',
    'XOM': 'Energy, Materials & Utilities',
}

ACTIVE_SECTORS = (
    'Financial Services',
)

ACTIVE_TICKERS = (
    'BLK',
    'BRK-B',
    'MA',
    'SPGI',
    'V',
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
        'GOOG', 
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
        'RTX',
    ),
    'EnergyA':(
        'CVX',
        'GEV',
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
}


FINANCIAL_POSITIONS_BY_GROUP = {
    'TechA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'commercial_paper',
            'long_term_debt_current',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },
    'TechB': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },
    'TechC': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },
    'TechD': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },
    # Add to FINANCIAL_POSITIONS_BY_GROUP — one starter group per remaining sector.
# Group names use an "A" suffix so you can split a sector later (like TechA–TechD).

    # ---------- Communication ----------
    'CommA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',     # only for reinvestment_rate = (R&D + capex) / revenue
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
            # 'content_investment',         # if available – content_or_network_investment_intensity
        ),
    },

    # ---------- Consumer Discretionary ----------
    'DiscA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
            'inventory',                    # inventory_turnover
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },

    # ---------- Consumer Staples ----------  (identical KPI needs to Discretionary)
    'StapA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
            'inventory',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },

    # ---------- Healthcare ----------  (same shape as the Technology groups)
    'HealthA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },

    # ---------- Industrials ----------  (gross margin + inventory turnover)
    'IndA': {
        'income_statement': (
            'revenue',
            'cost_of_revenue',
            'gross_profit',
            'research_and_development',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
            'inventory',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },

    # ---------- Energy, Materials & Utilities ----------  (no gross_margin / inventory_turnover)
    'EnergyA': {
        'income_statement': (
            'revenue',
            'research_and_development',      # only for reinvestment_rate
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',          # also covers free_cash_flow_after_capex_margin (def. still open)
        ),
    },
    'EnergyB': {
        'income_statement': (
            'revenue',
            'research_and_development',      # only for reinvestment_rate
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',          # also covers free_cash_flow_after_capex_margin (def. still open)
        ),
    },

    # ---------- Financial Services ----------  (non-bank: Visa, Mastercard, BlackRock, ...)
    'FinA': {
        'income_statement': (
            'revenue',
            'operating_income',
            'income_before_tax',
            'income_tax',
            'net_income',
            # 'operating_expenses',          # if available – inverse cost_to_income_ratio
        ),
        'balance_sheet': (
            'cash_and_cash_equivalents',     # needed by net_debt_to_assets
            'total_assets',
            'total_equity',
            'short_term_debt',
            'long_term_debt',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
            # 'acquisitions',                # if available – acquisition_intensity
        ),
    },

    # ---------- Banks ----------  (KPIs diverge most; several inputs are "if available")
    'BankA': {
        'income_statement': (
            'revenue',                       # total revenue (net interest income + noninterest income)
            'net_interest_income',           # if available – net_interest_margin
            'noninterest_expense',           # efficiency_ratio, noninterest_expense_to_revenue
            'net_income',
            'income_before_tax',
            'income_tax',
        ),
        'balance_sheet': (
            'total_assets',
            'total_equity',                  # equity_to_assets, assets_to_equity, ROE
            'total_loans',                   # if available – loan_growth_yoy
            'total_deposits',                # if available – deposit_growth_yoy
            'retained_earnings',             # capital_retention
            # 'allowance_for_credit_losses', # if available – provision_coverage
            # 'non_performing_loans',        # rarely tagged – provision_coverage
            # CET1 / Tier 1 ratios are regulatory disclosures, not statement lines
        ),
        'cash_flow_statement': (
            'operating_cash_flow',           # "only if meaningful" for banks
            # 'dividends_paid',              # alternative basis for capital_retention
        ),
    },
}

FINANCIAL_POSITION_SIGN_RULES = {
    'capital_expenditure': 'store_positive_absolute_value'
}


FINANCIAL_ITEMS_BY_GROUP = {
    'TechA': {
        'revenue': (
            'RevenueFromContractWithCustomerExcludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfGoodsAndServicesSold',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
        ),
        'commercial_paper': (
            'CommercialPaper',
        ),
        'long_term_debt_current': (
            'LongTermDebtCurrent',
        ),
        'short_term_debt': (),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
        ),
    },
    'TechB': {
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
            'CostOfGoodsAndServicesSold',
            'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'DebtCurrent',
            'ShortTermBorrowings',
            'LongTermDebtCurrent',
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebtAndCapitalLeaseObligations',
            'ConvertibleLongTermNotesPayable',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
        ),
    },
    'TechC': {
        'revenue': (
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
        ),
        'cost_of_revenue': (
            'CostOfGoodsAndServicesSold',
            'CostOfRevenue',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
        ),
    },
    'TechD': {
        'revenue': (
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
        ),
        'cost_of_revenue': (
            'CostOfGoodsAndServicesSold',
            'CostOfRevenue',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
            'ConvertibleDebtCurrent',
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
            'NotesPayableCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermNotesAndLoans',
            'LongTermDebtAndFinanceLeaseObligationsNoncurrent',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
        ),
    },
    'CommA': {
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
            'ConvertibleDebtCurrent',
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
            'NotesPayableCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermNotesAndLoans',
            'LongTermDebtAndFinanceLeaseObligationsNoncurrent',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherProductiveAssets',
        ),
    },
    'DiscA':{
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
            "CostOfGoodsAndServicesSold",
            'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
            'ConvertibleDebtCurrent',
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
            'NotesPayableCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermNotesAndLoans',
            'LongTermDebtAndFinanceLeaseObligationsNoncurrent',
        ),
        'inventory':(
            'InventoryNet',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherProductiveAssets',
        ),
    },
    'StapA':{
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
            "CostOfGoodsAndServicesSold",
            'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
            'IncomeLossAttributableToParent',
            'IncomeLossIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
            'ConvertibleDebtCurrent',
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
            'NotesPayableCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermNotesAndLoans',
            'LongTermDebtAndFinanceLeaseObligationsNoncurrent',
        ),
        'inventory':(
            'InventoryNet',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherProductiveAssets',
        ),
    },
    'HealthA': {
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
            'CostOfGoodsAndServicesSold',
            'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
            'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'DebtCurrent',
            'ShortTermBorrowings',
            'LongTermDebtCurrent',
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebtAndCapitalLeaseObligations',
            'ConvertibleLongTermNotesPayable',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherPropertyPlantAndEquipment',
        ),
    },
    'IndA':{
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'cost_of_revenue': (
            'CostOfRevenue',
            "CostOfGoodsAndServicesSold",
            'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
        ),
        'gross_profit': (
            'GrossProfit',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
            'IncomeLossAttributableToParent',
            'IncomeLossIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
            'ConvertibleDebtCurrent',
            'DebtCurrent',
            'LongTermDebtCurrent',
            'ShortTermBorrowings',
            'NotesPayableCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebt',
            'LongTermDebtAndCapitalLeaseObligations',
            'LongTermNotesAndLoans',
            'LongTermDebtAndFinanceLeaseObligationsNoncurrent',
        ),
        'inventory':(
            'InventoryNet',
            'InventoryNetOfAllowancesCustomerAdvancesAndProgressBillings',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherProductiveAssets',
        ),
    },
    'EnergyA': {
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
            'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
            'DebtCurrent',
            'ShortTermBorrowings',
            'LongTermDebtCurrent',
            'LongTermDebtAndCapitalLeaseObligationsCurrent',
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebtAndCapitalLeaseObligations',
            'ConvertibleLongTermNotesPayable',
            'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherPropertyPlantAndEquipment',
        ),
    },
    'EnergyB': {
        'revenue': (
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
        ),
        'research_and_development': (
            'ResearchAndDevelopmentExpense',
            'ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost',
        ),
        'operating_income': (
            'OperatingIncomeLoss',
        ),
        'income_before_tax': (
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax': (
            'IncomeTaxExpenseBenefit',
        ),
        'net_income': (
            'NetIncomeLoss',
            'ProfitLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
        ),
        'cash_and_cash_equivalents': (
            'CashAndCashEquivalentsAtCarryingValue',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
        ),
        'total_assets': (
            'Assets',
        ),
        'total_equity': (
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt': (
        ),
        'long_term_debt': (
            'LongTermDebtNoncurrent',
            'LongTermDebtAndCapitalLeaseObligations',
            'ConvertibleLongTermNotesPayable',
            'LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities',
        ),
        'operating_cash_flow': (
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ),
        'capital_expenditure': (
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
            'PaymentsToAcquireOtherPropertyPlantAndEquipment',
        ),
    },
    'FinA': {
        'revenue': (
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'Revenues',
        ),
        'operating_income':(
            'OperatingIncomeLoss',
        ),
        'income_before_tax':(
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        ),
        'income_tax':(
            'IncomeTaxExpenseBenefit',
        ),
        'net_income':(
            'NetIncomeLoss',
            'ProfitLoss',
        ),
        # 'operating_expenses',          # if available – inverse cost_to_income_ratio
        'cash_and_cash_equivalents':(
            'CashAndCashEquivalentsAtCarryingValue',
        ),     # needed by net_debt_to_assets
        'total_assets':(
            'Assets',
        ),
        'total_equity':(
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ),
        'short_term_debt':(
            'LongTermDebtCurrent',
            'DebtCurrent',
        ),
        'long_term_debt':(
            'LongTermDebtNoncurrent',
            'LongTermDebt',
        ),
        'operating_cash_flow':(
            'NetCashProvidedByUsedInOperatingActivities',
        ),
        'capital_expenditure':(
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
        ),
            # 'acquisitions',                # if available – acquisition_intensity
    },
}


INLINE_FINANCIAL_ITEMS_BY_TICKER = {
    'AAPL': {
        'commercial_paper': {
            'concepts': (
                'CommercialPaper',
            ),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'ShortTermDebtTypeAxis': 'CommercialPaperMember',
            },
        },
    },
    'AMZN': {
        'research_and_development': {
            'concepts': (
                'TechnologyAndInfrastructureExpense',
                'TechnologyAndContentExpense',
            ),
            'statement_type': 'income_statement',
        },
    },
    'BRK-B': {
        'cash_and_cash_equivalents': {
            'concepts': (
                'CashAndCashEquivalentsAtCarryingValue',
            ),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'ProductOrServiceAxis': 'InsuranceAndOtherMember',
            },
        },
    },
    'CAT':{
        'long_debt_machine': {
            'concepts': (
                'LongTermDebtAndCapitalLeaseObligations',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'MachineryPowerEnergyMember',
                    'MachineryEnergyTransportationMember',
                ),
            },
        },
        'long_debt_finance': {
            'concepts': (
                'LongTermDebtAndCapitalLeaseObligations',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'FinancialProductsMember',
                ),
            },
        },
        'short_debt_machine': {
            'concepts': (
                'LongTermDebtAndCapitalLeaseObligationsCurrent',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'MachineryPowerEnergyMember',
                    'MachineryEnergyTransportationMember',
                ),
            },
        },
        'short_debt_finance': {
            'concepts': (
                'LongTermDebtAndCapitalLeaseObligationsCurrent',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'FinancialProductsMember',
                ),
            },
        },
    },
    'CVX':{
        'cost_of_revenue': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
        },
        'operating_expense': {
            'concepts': (
                'OperatingCostsAndExpenses',
            ),
            'statement_type': 'income_statement',
        },
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'exploration_expense': {
            'concepts': (
                'ExplorationExpense',
            ),
            'statement_type': 'income_statement',
        },
        'depr_amo': {
            'concepts': (
                'DepreciationDepletionAndAmortization',
            ),
            'statement_type': 'income_statement',
        },
        'taxes': {
            'concepts': (
                'TaxesOther',
            ),
            'statement_type': 'income_statement',
        },
    },
    'DIS':{
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ), 
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                ),
            },
        },
    },
    'GE':{
        'long_term_debt': {
            'concepts': (
                'FinanceLeaseLiabilityNoncurrentAndOtherLongTermDebt',
            ),
            'statement_type': 'income_statement',
        },
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                ),
            },
        },
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'restru': {
            'concepts': (
                'RestructuringAndRelatedCostIncurredCost',
                'RestructuringCharges'
            ),
            'statement_type': 'income_statement',
        },
        'insurance': {
            'concepts': (
                'InvestmentContractsInsuranceLossesInsuranceAnnuityBenefitsAndOther',
                'InvestmentContractsInsuranceLossesAndInsuranceAnnuityBenefits',
            ),
            'statement_type': 'income_statement',
        },
        'impairments': {
            'concepts': (
                'GoodwillImpairmentLoss',
            ),
            'statement_type': 'income_statement',
        },

    },
    'IBM': {
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'intel_prop': {
            'concepts': (
                'IntellectualPropertyAndCustomDevelopmentIncome',
            ),
            'statement_type': 'income_statement',
        },
        'other_income_exp': {
            'concepts': (
                'OtherExpenseAndIncome',
                'OtherIncomeAndExpense',
            ),
            'statement_type': 'income_statement',
        },
    },
    'INTU': {
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
                'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                    'ProductAndOtherMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
                'CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                    'ServiceAndOtherMember',
                ),
            },
        },
        'cost_of_amo': {
            'concepts': (
                'CostOfGoodsAndServicesSoldAmortization',
            ),
            'statement_type': 'income_statement',
        },
    },
    'JNJ': {
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'impairment': {
            'concepts': (
                'ResearchAndDevelopmentInProcess1',
                'ResearchAndDevelopmentInProcess',
            ),
            'statement_type': 'income_statement',
        },
        'restru': {
            'concepts': (
                'RestructuringCharges',
            ),
            'statement_type': 'income_statement',
        },
    },
    'KLAC': {
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'impairment': {
            'concepts': (
                'AssetImpairmentCharges',
            ),
            'statement_type': 'income_statement',
        },
    },
    'LRCX': {
        'cost_of_revenue': {
            'concepts': (
                'CostOfGoodsAndServicesSoldExcludingRestructuringCharges',
            ),
            'statement_type': 'income_statement',
        },
    },
    'LLY': {
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'impairment': {
            'concepts': (
                'RestructuringSettlementAndImpairmentProvisions',
            ),
            'statement_type': 'income_statement',
        },
        'restru': {
            'concepts': (
                'ResearchAndDevelopmentAssetAcquiredOtherThanThroughBusinessCombinationWrittenOff',
                'AcquiredInProcessResearchAndDevelopment',
            ),
            'statement_type': 'income_statement',
        },
    },
    "MCD":{
        'cost_of_revenue': {
            'concepts': (
                'Franchisedrestaurantsoccupancyexpenses',
            ),
            'statement_type': 'income_statement',
        },
        'income_before_tax':{
            'concepts':(
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxes',
            ),
            'statement_type': 'income_statement',
        },
    },
    'MRK': {
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'restru': {
            'concepts': (
                'RestructuringCharges',
            ),
            'statement_type': 'income_statement',
        },
    },
    'NEE': {
        'capital_expenditure': {
            'concepts': (
                'CapitalExpendituresOfFPL',
                'CapitalExpendituresOfFPLSegment',
            ),
            'statement_type': 'cash_flow_statement',
        },
        'current_debt': {
            'concepts': (
                'LongTermDebtCurrent',
            ),
            'statement_type': 'cash_flow_statement',
        },
        'commercial_paper': {
            'concepts': (
                'CommercialPaper',
            ),
            'statement_type': 'cash_flow_statement',
        },
        'other_short_term': {
            'concepts': (
                'OtherShortTermBorrowings',
            ),
            'statement_type': 'cash_flow_statement',
        },
    },
    'NFLX': {
        'research_and_development': {
            'concepts': (
                'TechnologyandDevelopmentExpense',
            ),
            'statement_type': 'income_statement',
        },
    },
    'NVDA': {
        'capital_expenditure': {
            'concepts': (
                'PurchasesOfPropertyAndEquipmentAndIntangibleAssets',
            ),
            'statement_type': 'cash_flow_statement',
        },
    },
    'ORCL': {
        'cloud_services_and_license_support_cost': {
            'concepts': (
                'CloudServicesAndLicenseSupportExpenses',
                'CloudAndSoftwareExpenses',
            ),
            'statement_type': 'income_statement',
        },
        'hardware_cost': {
            'concepts': (
                'HardwareExpenses',
            ),
            'statement_type': 'income_statement',
        },
        'services_cost': {
            'concepts': (
                'ServicesExpense',
            ),
            'statement_type': 'income_statement',
        },
        'income_before_tax': {
            'concepts': (
                'IncomeLossFromContinuingOperationsIncludingNoncontrollingInterestBeforeIncomeTaxesExtraordinaryItems',
            ),
            'statement_type': 'income_statement',
        },
    },
    'PG': {
        'income_before_tax': {
            'concepts': (
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxes',
            ),
            'statement_type': 'income_statement',
        },
    },
    'RTX':{
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                ),
            },
        },
    },
    'T':{
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                    'EquipmentMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'OtherCostOfOperatingRevenue',
            ),
            'statement_type': 'income_statement',
        },
    },
    'TJX':{
        'operating_income': {
            'concepts': (
                'OperatingIncomeLoss',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ConsolidationItemsAxis': (
                    'OperatingSegmentsMember',
                ),
            },
        },
    },
    'TMO':{
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                ),
            },
        },
    },
    'VZ':{
        'cost_of_product': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ProductMember',
                ),
            },
        },
        'cost_of_service': {
            'concepts': (
                'CostOfGoodsAndServicesSold',
            ),
            'statement_type': 'income_statement',
            'required_axis_member': {
                'ProductOrServiceAxis': (
                    'ServiceMember',
                ),
            },
        },
    },
    'XOM':{
        'cost_of_revenue': {
            'concepts': (
                'CrudeOilAndProductPurchases',
            ),
            'statement_type': 'income_statement',
        },
        'operating_expense': {
            'concepts': (
                'ProductionAndManufacturingExpenses',
            ),
            'statement_type': 'income_statement',
        },
        'selling_general': {
            'concepts': (
                'SellingGeneralAndAdministrativeExpense',
            ),
            'statement_type': 'income_statement',
        },
        'exploration_expense': {
            'concepts': (
                'ExplorationExpense',
            ),
            'statement_type': 'income_statement',
        },
        'depr_amo': {
            'concepts': (
                'DepreciationDepletionAndAmortization',
            ),
            'statement_type': 'income_statement',
        },
        'taxes': {
            'concepts': (
                'TaxesOther',
            ),
            'statement_type': 'income_statement',
        },
    },
}


CALCULATED_FINANCIAL_ITEMS_BY_GROUP = {
    'TechA': {
        'short_term_debt': {
            'concept': 'calc_short_term_debt',
                'components': (
                    ('commercial_paper',1,),
                    ('long_term_debt_current',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': True,
            'overwrite_existing': True,
        },
    },
    'TechC': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'TechD': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'CommA': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'DiscA': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'StapA': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'HealthA': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'IndA': {
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
}


CALCULATED_FINANCIAL_ITEMS_BY_TICKER = {
    'CAT': {
        'long_term_debt': {
            'concept': 'calc_long_term_debt',
                'components': (
                    ('long_debt_machine',1,),
                    ('long_debt_finance',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
        'short_term_debt': {
            'concept': 'calc_short_term_debt',
                'components': (
                    ('short_debt_machine',1,),
                    ('short_debt_finance',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'CVX':{
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                    ('operating_expense',-1,),
                    ('selling_general',-1,),
                    ('exploration_expense',-1,),
                    ('depr_amo',-1,),
                    ('taxes',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'DIS': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'GE': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('restru',-1,),
                    ('insurance',-1,),
                    ('impairments',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'IBM': {
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('intel_prop',1,),
                    ('other_income_exp',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'INTU': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                    ('cost_of_amo',1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'JNJ': {
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('impairment',-1,),
                    ('restru',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'KLAC': {
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('impairment',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'LLY': {
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('impairment',-1,),
                    ('restru',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'MRK': {
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('gross_profit',1,),
                    ('selling_general',-1,),
                    ('research_and_development',-1,),
                    ('restru',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'NEE': {
        'short_term_debt': {
            'concept': 'calc_short_term',
                'components': (
                    ('commercial_paper',1,),
                    ('current_debt',1,),
                    ('other_short_term',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'ORCL': {
        'cost_of_revenue': {
            'concept': 'calc_orcl_cost_of_revenue',
                'components': (
                    ('cloud_services_and_license_support_cost',1,),
                    ('hardware_cost',1,),
                    ('services_cost',1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
        'gross_profit': {
            'concept': 'calc_gross_profit',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                ),
            'missing_components_as_zero': False,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
        },
    },
    'RTX': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'T': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'TMO': {
        'cost_of_revenue': {
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'VZ': {
        'cost_of_revenue': { 
            'concept': 'calc_cost_of_revenue',
                'components': (
                    ('cost_of_service',1,),
                    ('cost_of_product',1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
    'XOM':{
        'operating_income': {
            'concept': 'calc_operating_income',
                'components': (
                    ('revenue',1,),
                    ('cost_of_revenue',-1,),
                    ('operating_expense',-1,),
                    ('selling_general',-1,),
                    ('exploration_expense',-1,),
                    ('depr_amo',-1,),
                    ('taxes',-1,),
                ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': False,
            'overwrite_existing': False,
            'quality': 'company_specific_calculation',
        },
    },
}

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
