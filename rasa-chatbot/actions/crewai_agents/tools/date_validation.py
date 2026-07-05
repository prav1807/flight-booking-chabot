import json
from datetime import datetime, date

from crewai.tools import BaseTool


class DateValidationTool(BaseTool):
    name: str = "Date Validation Tool"
    description: str = (
        "Validates flight booking dates. "
        "Input must be a JSON string with keys: "
        "'departure_date' (YYYY-MM-DD string), "
        "'return_date' (YYYY-MM-DD string or null), "
        "'trip_type' ('one-way' or 'return'). "
        "Returns a JSON object with 'valid' (bool) and 'errors' (list of problem descriptions)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
        except (json.JSONDecodeError, TypeError):
            return json.dumps({"valid": False, "errors": ["Invalid input. Provide a JSON string."]})

        departure_date = data.get("departure_date")
        return_date = data.get("return_date")
        trip_type = str(data.get("trip_type", "one-way")).lower()

        errors = []
        today = date.today()
        dep_date = None

        # Validate departure date
        if not departure_date:
            errors.append("Departure date is missing.")
        else:
            try:
                dep_date = datetime.strptime(departure_date, "%Y-%m-%d").date()
                if dep_date < today:
                    errors.append(
                        f"Departure date {departure_date} is in the past. "
                        "Please choose a future date."
                    )
            except ValueError:
                errors.append(
                    f"Departure date '{departure_date}' is not a valid date. "
                    "Expected format: YYYY-MM-DD."
                )

        # Validate return date for return trips
        if "return" in trip_type:
            if not return_date:
                errors.append("A return date is required for a return trip but is missing.")
            else:
                try:
                    ret_date = datetime.strptime(return_date, "%Y-%m-%d").date()
                    if ret_date < today:
                        errors.append(f"Return date {return_date} is in the past.")
                    if dep_date and ret_date <= dep_date:
                        errors.append(
                            f"Return date {return_date} must be after "
                            f"departure date {departure_date}."
                        )
                except ValueError:
                    errors.append(
                        f"Return date '{return_date}' is not a valid date. "
                        "Expected format: YYYY-MM-DD."
                    )

        return json.dumps({"valid": len(errors) == 0, "errors": errors})
