"""concepts.py — the us-gaap / iXBRL concept maps. PURE DATA, no logic.

Extracted verbatim from the old `A_config.py`, which mixed ~200 lines you actually read
(paths, universe, risk-free rate) with ~2,300 lines of literal concept tables you never do.
Nothing here imports anything or references any other module.

  FINANCIAL_POSITIONS_BY_GROUP        canonical position list per implementation group
  FINANCIAL_POSITION_SIGN_RULES       positions stored with a flipped sign
  FINANCIAL_ITEMS_BY_GROUP            us-gaap concepts per (group, position)
  INLINE_FINANCIAL_ITEMS_BY_TICKER    iXBRL fallbacks where companyfacts is silent
  CALCULATED_FINANCIAL_ITEMS_BY_GROUP derived positions (e.g. gross_profit = rev - cost)
  CALCULATED_FINANCIAL_ITEMS_BY_TICKER  per-ticker overrides of the above
"""

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

    # ---------- Communication ----------
    'CommA': {
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
            # 'content_investment',         # if available – content_or_network_investment_intensity
        ),
    },

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
            'inventory',                    
        ),
        'cash_flow_statement': (
            'operating_cash_flow',
            'capital_expenditure',
        ),
    },

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

    'EnergyA': {
        'income_statement': (
            'revenue',
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
    'EnergyB': {
        'income_statement': (
            'revenue',
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

    'BankA': {
        'income_statement': (
            'revenue',                       
            'net_interest_income',          
            'noninterest_expense',           
            'net_income',
            'income_before_tax',
            'income_tax',
        ),
        'balance_sheet': (
            'total_assets',
            'total_equity',                  
            'total_loans',                   
            'total_deposits',                
            'retained_earnings',             
            'allowance_for_credit_losses',
        ),
        'cash_flow_statement': (
            'operating_cash_flow',          
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
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
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
    'BankA': {
        'revenue':(
            'RevenuesNetOfInterestExpense',
            'Revenues',
        ),                      
        'net_interest_income':(
            'InterestIncomeExpenseNet',
        ),           
        'noninterest_expense':(
            'NoninterestExpense',
        ),           
        'net_income':(
            'NetIncomeLoss',
        ),
        'income_before_tax':(
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
        ),
        'income_tax':(
            'IncomeTaxExpenseBenefit',
        ),
        'total_assets':(
            'Assets',
        ),
        'total_equity':(
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
            'StockholdersEquity',
        ),                  
        'total_loans':(
            'FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss',
            'NotesReceivableNet',
            'LoansAndLeasesReceivableNetReportedAmount',
        ),                  
        'total_deposits':(
            'Deposits',
        ),                
        'retained_earnings':(
            'RetainedEarningsAccumulatedDeficit',
        ),            
        'allowance_for_credit_losses':(
            'FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest',
            'FinancingReceivableAllowanceForCreditLosses',
            'LoansAndLeasesReceivableAllowance',
        ), 
        'operating_cash_flow':(
            'NetCashProvidedByUsedInOperatingActivities',
        ),
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
    'AXP': {
        'card_member_loans': {
            'concepts': ('NotesReceivableNet',),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'FinancingReceivableRecordedInvestmentByClassOfFinancingReceivableAxis': ('CardmemberLoansMember', 'CardMemberLoansMember', 'CardBalancesMember')
            },
        },
        'card_member_loans_held_for_sale': {
            'concepts': ('LoansReceivableHeldForSaleAmount',),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'FinancingReceivableRecordedInvestmentByClassOfFinancingReceivableAxis': ('CardmemberLoansMember', 'CardMemberLoansMember', 'CardBalancesMember')
            },
        },
        'other_loans': {
            'concepts': ('NotesReceivableNet',),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'FinancingReceivableRecordedInvestmentByClassOfFinancingReceivableAxis': 'OtherLoansMember',
            },
        },
        'allowance_for_credit_losses': {
            'concepts': ('FinancingReceivableAllowanceForCreditLosses',),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'FinancingReceivableRecordedInvestmentByClassOfFinancingReceivableAxis': ('CardmemberLoansMember', 'CardMemberLoansMember', 'CardBalancesMember'),
            },
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
        'long_term_debt': {
            'concepts': (
                'DebtAndCapitalLeaseObligations',
            ),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'ProductOrServiceAxis': 'RailroadUtilitiesAndEnergyMember',
            },
        },
        'short_term_debt': {
            'concepts': (
                'DebtAndCapitalLeaseObligations',
            ),
            'statement_type': 'balance_sheet',
            'required_axis_member': {
                'ProductOrServiceAxis': 'InsuranceAndOtherMember',
            },
        },
        'cost_expenses': {
            'concepts': (
                'CostsAndExpenses',
            ),
            'statement_type': 'income_statement',
        },
    },
    'C': {
        'revenue': {
            'concepts': (
                'Revenues',
            ),
            'statement_type': 'income_statement',
        },
        'net_interest_income': {
            'concepts': (
                'InterestIncomeExpenseNet',
            ),
            'statement_type': 'income_statement',
        },
        'noninterest_expense': {
            'concepts': (
                'NoninterestExpense',
            ),
            'statement_type': 'income_statement',
        },
        'net_income': {
            'concepts': (
                'NetIncomeLoss',
            ),
            'statement_type': 'income_statement',
        },
        'income_before_tax': {
            'concepts': (
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
            ),
            'statement_type': 'income_statement',
        },
        'income_tax': {
            'concepts': (
                'IncomeTaxExpenseBenefit',
            ),
            'statement_type': 'income_statement',
        },
        'total_assets': {
            'concepts': (
                'Assets',
            ),
            'statement_type': 'balance_sheet',
        },
        'total_equity': {
            'concepts': (
                'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
            ),
            'statement_type': 'balance_sheet',
        },
        'total_loans': {
            'concepts': (
                'FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss',
            ),
            'statement_type': 'balance_sheet',
        },
        'total_deposits': {
            'concepts': (
                'Deposits',
            ),
            'statement_type': 'balance_sheet',
        },
        'retained_earnings': {
            'concepts': (
                'RetainedEarningsAccumulatedDeficit',
            ),
            'statement_type': 'balance_sheet',
        },
        'allowance_for_credit_losses':{
            'concepts':(
                'FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest',
                'FinancingReceivableAllowanceForCreditLosses',
            ),
            'statement_type': 'balance_sheet',
        }, 
        'operating_cash_flow': {
            'concepts': (
                'NetCashProvidedByUsedInOperatingActivities',
            ),
            'statement_type': 'cash_flow_statement',
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
    'SPGI': {
        'revenue': {
            'concepts': (
                'RevenueFromContractWithCustomerExcludingAssessedTax',
                'Revenues',
            ),
            'statement_type': 'income_statement',
        },
        'operating_income': {
            'concepts': (
                'OperatingIncomeLoss',
            ),
            'statement_type': 'income_statement',
        },
        'income_before_tax': {
            'concepts': (
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
            ),
            'statement_type': 'income_statement',
        },
        'income_tax': {
            'concepts': (
                'IncomeTaxExpenseBenefit',
            ),
            'statement_type': 'income_statement',
        },
        'net_income': {
            'concepts': (
                'NetIncomeLoss',
                'ProfitLoss',
            ),
            'statement_type': 'income_statement',
        },
        'cash_and_cash_equivalents': {
            'concepts': (
                'CashAndCashEquivalentsAtCarryingValue',
            ),
            'statement_type': 'balance_sheet',
        },
        'total_assets': {
            'concepts': (
                'Assets',
            ),
            'statement_type': 'balance_sheet',
        },
        'total_equity': {
            'concepts': (
                'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
                'StockholdersEquity',
            ),
            'statement_type': 'balance_sheet',
        },
        'short_term_debt': {
            'concepts': (
                'DebtCurrent',
                'LongTermDebtCurrent',
            ),
            'statement_type': 'balance_sheet',
        },
        'long_term_debt': {
            'concepts': (
                'LongTermDebtNoncurrent',
                'LongTermDebt',
            ),
            'statement_type': 'balance_sheet',
        },
        'operating_cash_flow': {
            'concepts': (
                'NetCashProvidedByUsedInOperatingActivities',
            ),
            'statement_type': 'cash_flow_statement',
        },
        'capital_expenditure': {
            'concepts': (
                'PaymentsToAcquireProductiveAssets',
                'PaymentsToAcquirePropertyPlantAndEquipment',
            ),
            'statement_type': 'cash_flow_statement',
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
    'WFC':{
        'total_loans': {
            'concepts': (
                'FinancingReceivableAndNetInvestmentInLeaseExcludingAccruedInterestBeforeAllowanceForCreditLoss',
            ),
            'statement_type': 'balance_sheet',
        },
        'allowance_for_credit_losses': {
            'concepts': (
                'FinancingReceivableAndNetInvestmentInLeaseAllowanceForLoanLossesExcludingAccruedInterest',
            ),
            'statement_type': 'balance_sheet',
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
    'AXP': {
        'total_loans': {
            'concept': 'calc_total_loans',
            'components': (
                ('card_member_loans',1,),
                ('card_member_loans_held_for_sale',1,),
                ('other_loans',1,),
            ),
            'missing_components_as_zero': True,
            'require_at_least_one_component': True,
            'overwrite_existing': True,
            'quality': 'company_specific_calculation',
        },
    },

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
