def format_currency(value, symbol="€"):
    return f"{symbol}{value:,.2f}"

def validate_isin(isin):
    return isinstance(isin, str) and len(isin) == 12

def format_date(date, fmt="%d/%m/%Y"):
    return date.strftime(fmt)