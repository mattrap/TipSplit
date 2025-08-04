from datetime import datetime, timedelta

# All pay periods for 2025 with deposit dates
pay_periods = {
    "2025_01": {
        "range": "05/01/2025 - 18/01/2025",
        "deposit": "23/01/2025"
    },
    "2025_02": {
        "range": "19/01/2025 - 01/02/2025",
        "deposit": "06/02/2025"
    },
    "2025_03": {
        "range": "02/02/2025 - 15/02/2025",
        "deposit": "20/02/2025"
    },
    "2025_04": {
        "range": "16/02/2025 - 01/03/2025",
        "deposit": "06/03/2025"
    },
    "2025_05": {
        "range": "02/03/2025 - 15/03/2025",
        "deposit": "20/03/2025"
    },
    "2025_06": {
        "range": "16/03/2025 - 29/03/2025",
        "deposit": "03/04/2025"
    },
    "2025_07": {
        "range": "30/03/2025 - 12/04/2025",
        "deposit": "17/04/2025"
    },
    "2025_08": {
        "range": "13/04/2025 - 26/04/2025",
        "deposit": "01/05/2025"
    },
    "2025_09": {
        "range": "27/04/2025 - 10/05/2025",
        "deposit": "15/05/2025"
    },
    "2025_10": {
        "range": "11/05/2025 - 24/05/2025",
        "deposit": "29/05/2025"
    },
    "2025_11": {
        "range": "25/05/2025 - 07/06/2025",
        "deposit": "12/06/2025"
    },
    "2025_12": {
        "range": "08/06/2025 - 21/06/2025",
        "deposit": "26/06/2025"
    },
    "2025_13": {
        "range": "22/06/2025 - 05/07/2025",
        "deposit": "10/07/2025"
    },
    "2025_14": {
        "range": "06/07/2025 - 19/07/2025",
        "deposit": "24/07/2025"
    },
    "2025_15": {
        "range": "20/07/2025 - 02/08/2025",
        "deposit": "07/08/2025"
    },
    "2025_16": {
        "range": "03/08/2025 - 16/08/2025",
        "deposit": "21/08/2025"
    },
    "2025_17": {
        "range": "17/08/2025 - 30/08/2025",
        "deposit": "04/09/2025"
    },
    "2025_18": {
        "range": "31/08/2025 - 13/09/2025",
        "deposit": "18/09/2025"
    },
    "2025_19": {
        "range": "14/09/2025 - 27/09/2025",
        "deposit": "02/10/2025"
    },
    "2025_20": {
        "range": "28/09/2025 - 11/10/2025",
        "deposit": "16/10/2025"
    },
    "2025_21": {
        "range": "12/10/2025 - 25/10/2025",
        "deposit": "30/10/2025"
    },
    "2025_22": {
        "range": "26/10/2025 - 08/11/2025",
        "deposit": "13/11/2025"
    },
    "2025_23": {
        "range": "09/11/2025 - 22/11/2025",
        "deposit": "27/11/2025"
    },
    "2025_24": {
        "range": "23/11/2025 - 06/12/2025",
        "deposit": "11/12/2025"
    },
    "2025_25": {
        "range": "07/12/2025 - 20/12/2025",
        "deposit": "25/12/2025"
    },
    "2025_26": {
        "range": "21/12/2025 - 03/01/2026",
        "deposit": "08/01/2026"
    }
}

def get_period_from_date(date: datetime) -> tuple[str, dict] | tuple[None, None]:
    for key, data in pay_periods.items():
        start_str, end_str = data["range"].split(" - ")
        start = datetime.strptime(start_str, "%d/%m/%Y")
        end = datetime.strptime(end_str, "%d/%m/%Y")
        if start <= date <= end:
            return key, data
    return None, None

def get_selected_period(selected_dt):
    for key, period in pay_periods.items():
        start_str, end_str = period["range"].split(" - ")
        start = datetime.strptime(start_str, "%d/%m/%Y")
        end = datetime.strptime(end_str, "%d/%m/%Y")
        if start <= selected_dt <= end:
            return key, period
    return None, None
    # returns ('2025_14', {'range': '06/07/2025 - 19/07/2025', 'deposit': '24/07/2025'})


