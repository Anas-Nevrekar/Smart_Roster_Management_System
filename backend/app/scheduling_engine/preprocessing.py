
import calendar
from datetime import date, timedelta


def build_daily_requirements(dataset, month, year):
    """
    Generate daily brand-process staffing requirements.

    Returns:
        A list containing one entry per operating
        brand-process combination per date.
    """

    # Validate month
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12")

    # Lookup public holidays
    public_holidays = {
        holiday["holiday_date"]
        for holiday in dataset["public_holidays"]
    }

    # Lookup active brands and processes
    active_brands = {
        brand["brand_id"]
        for brand in dataset["brands"]
        if brand["is_active"]
    }

    active_processes = {
        process["process_id"]
        for process in dataset["processes"]
        if process["is_active"]
    }

    requirements = []

    # Get number of days in selected month
    total_days = calendar.monthrange(year, month)[1]

    # Iterate through every date
    for day in range(1, total_days + 1):

        current_date = date(year, month, day)

        date_string = current_date.isoformat()
        weekday = current_date.strftime("%A")

        is_public_holiday = date_string in public_holidays

        # Check every brand-process rule
        for rule in dataset["brand_process_rules"]:

            if not rule["is_active"]:
                continue

            brand_id = rule["brand_id"]
            process_id = rule["process_id"]

            # Skip inactive brands and processes
            if brand_id not in active_brands:
                continue

            if process_id not in active_processes:
                continue

            # Check operating calendar
            if is_public_holiday:

                if rule["public_holiday_policy"] != "operate":
                    continue

            else:

                if weekday not in rule["operating_days"]:
                    continue

            # Add staffing requirement
            requirements.append({
                "date": date_string,
                "weekday": weekday,
                "brand_id": brand_id,
                "process_id": process_id,
                "required_staffing": rule["minimum_staffing"]
            })

    return requirements
