import calendar
import json
import re
from datetime import date, datetime, timedelta
from difflib import get_close_matches

from crewai.tools import BaseTool


MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

WEEKDAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}

SPECIAL_DATES = {
    "christmas": (12, 25),
    "xmas": (12, 25),
    "new year": (1, 1),
    "new years": (1, 1),
    "halloween": (10, 31),
    "valentines": (2, 14),
    "valentine's day": (2, 14),
    "thanksgiving": (11, 28),  # approximate US Thanksgiving
}


def _next_occurrence(month: int, day: int, today: date) -> date:
    """Returns the next future occurrence of a given month/day."""
    candidate = date(today.year, month, day)
    if candidate <= today:
        candidate = date(today.year + 1, month, day)
    return candidate


def _add_months(d: date, months: int) -> date:
    """Adds N months to a date, clamping to the last valid day."""
    total_month = d.month + months
    year = d.year + (total_month - 1) // 12
    month = ((total_month - 1) % 12) + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class DateInterpreterTool(BaseTool):
    name: str = "Date Interpreter Tool"
    description: str = (
        "Interprets natural language date expressions and converts them to ISO format (YYYY-MM-DD). "
        "Input must be a JSON string with 'date_text' (natural language date string) "
        "and 'today' (current date as YYYY-MM-DD for relative calculations). "
        "Returns JSON with 'resolved' (bool), 'iso_date' (YYYY-MM-DD or null), 'explanation' (string)."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
            raw_text = str(data.get("date_text", "")).strip()
            today_str = data.get("today", date.today().isoformat())
            today = datetime.strptime(today_str, "%Y-%m-%d").date()
        except Exception:
            return json.dumps({"resolved": False, "iso_date": None, "explanation": "Invalid input format."})

        text = raw_text.lower().strip()

        # Already ISO format — nothing to do
        if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            return json.dumps({"resolved": True, "iso_date": text, "explanation": "Already in ISO format."})

        # ── Simple relative expressions ──────────────────────────────────────────
        if text == "today":
            return self._ok(today, "Today")
        if text == "tomorrow":
            return self._ok(today + timedelta(days=1), "Tomorrow")

        # "in X days / weeks / months"
        m = re.match(r"in (\d+)\s+(day|days|week|weeks|month|months)", text)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            if "day" in unit:
                d = today + timedelta(days=n)
            elif "week" in unit:
                d = today + timedelta(weeks=n)
            else:
                d = _add_months(today, n)
            return self._ok(d, f"In {n} {unit} from today")

        # ── Month-relative expressions ───────────────────────────────────────────
        if text == "next month":
            d = date(_add_months(today, 1).year, _add_months(today, 1).month, 1)
            return self._ok(d, "First day of next month")

        if re.search(r"\bend of next month\b", text):
            nm = _add_months(today, 1)
            d = date(nm.year, nm.month, calendar.monthrange(nm.year, nm.month)[1])
            return self._ok(d, "Last day of next month")

        if re.search(r"\bend of (this month|the month|month)\b", text):
            d = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
            return self._ok(d, "Last day of this month")

        # ── Next weekday ─────────────────────────────────────────────────────────
        m = re.match(r"next\s+(\w+)", text)
        if m and m.group(1) in WEEKDAY_NAMES:
            target = WEEKDAY_NAMES[m.group(1)]
            days_ahead = (target - today.weekday()) % 7 or 7
            return self._ok(today + timedelta(days=days_ahead), f"Next {m.group(1).title()}")

        # ── Special named holidays ───────────────────────────────────────────────
        for name, (month, day) in SPECIAL_DATES.items():
            if name in text:
                return self._ok(_next_occurrence(month, day, today), f"{name.title()}")

        # Fuzzy-match holiday names against individual words (catches typos like "chrismas", "xmass")
        holiday_keys = list(SPECIAL_DATES.keys())
        for word in text.split():
            if len(word) >= 4:
                matches = get_close_matches(word, holiday_keys, n=1, cutoff=0.75)
                if matches:
                    matched = matches[0]
                    month, day = SPECIAL_DATES[matched]
                    return self._ok(
                        _next_occurrence(month, day, today),
                        f"{matched.title()} (matched from '{word}')",
                    )

        # ── "[start/beginning/end] of [month]" ──────────────────────────────────
        for prefix, is_end in [("end of", True), ("beginning of", False), ("start of", False)]:
            if prefix in text:
                rest = text[text.index(prefix) + len(prefix):].strip().lstrip("next").strip()
                for mname, mnum in MONTH_NAMES.items():
                    if rest.startswith(mname):
                        year = today.year
                        if mnum < today.month or (mnum == today.month and today.day > 10):
                            year += 1
                        day = calendar.monthrange(year, mnum)[1] if is_end else 1
                        label = ("End" if is_end else "Start") + f" of {mname.title()} {year}"
                        return self._ok(date(year, mnum, day), label)

        # ── "[Month] [Day]" or "[Day] [Month]" ──────────────────────────────────
        for mname, mnum in MONTH_NAMES.items():
            # "july 15" / "july 15th"
            m = re.search(rf"{mname}\s+(\d{{1,2}})(st|nd|rd|th)?", text)
            if m:
                result = self._month_day(mnum, int(m.group(1)), today)
                if result:
                    return result
            # "15 july" / "15th july"
            m = re.search(rf"(\d{{1,2}})(st|nd|rd|th)?\s+{mname}", text)
            if m:
                result = self._month_day(mnum, int(m.group(1)), today)
                if result:
                    return result

        # ── Just a month name → first of that month ─────────────────────────────
        clean = text.replace("next ", "").strip()
        if clean in MONTH_NAMES:
            mnum = MONTH_NAMES[clean]
            year = today.year
            if mnum <= today.month:
                year += 1
            return self._ok(date(year, mnum, 1), f"First of {clean.title()} {year}")

        # ── Could not resolve ────────────────────────────────────────────────────
        return json.dumps({
            "resolved": False,
            "iso_date": None,
            "explanation": (
                f"Could not automatically interpret '{raw_text}'. "
                "Please ask the user for a specific date like '15 July 2027' or '2027-07-15'."
            ),
        })

    # ── Helpers ──────────────────────────────────────────────────────────────────

    def _ok(self, d: date, label: str) -> str:
        return json.dumps({"resolved": True, "iso_date": d.isoformat(), "explanation": label})

    def _month_day(self, month: int, day: int, today: date):
        try:
            candidate = date(today.year, month, day)
            if candidate <= today:
                candidate = date(today.year + 1, month, day)
            return self._ok(candidate, f"{calendar.month_name[month]} {day}, {candidate.year}")
        except ValueError:
            return None
