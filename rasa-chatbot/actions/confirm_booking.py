from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction


class ConfirmBooking(Action):
    def name(self) -> Text:
        return "confirm_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # confirmation = str(tracker.latest_message.get("text", "")).lower().strip()
        confirmation = tracker.get_slot("booking_confirmation")

        if not confirmation:
            confirmation = tracker.latest_message.get("text", "")

        confirmation = str(confirmation).lower().strip()

        if confirmation in ["yes", "y", "confirm", "confirmed", "proceed", "checkout", "confirm booking"]:
            dispatcher.utter_message(
                text=(
                    "Perfect. Your booking has been confirmed as a draft booking.\n\n"
                    "Next step will be checkout/payment integration."
                )
            )
            return [
                SlotSet("booking_confirmed", True),
                SlotSet("booking_confirmation", None),
                FollowupAction("save_booking_to_supabase"),
            ]

        if confirmation in ["no", "n", "cancel", "not now", "cancel booking"]:
            dispatcher.utter_message(
                text="No problem. I have not confirmed the booking."
            )
            return [
                SlotSet("booking_confirmed", False),
                SlotSet("booking_confirmation", None),
                FollowupAction("utter_anything_else"),
            ]

        dispatcher.utter_message(
            text="Please type confirm booking or cancel booking."
        )
        return []