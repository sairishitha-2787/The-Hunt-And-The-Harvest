// The questions both partners answer, in order.
// The 6 ISSP items use the wording and order of definitions.md (v39-v44);
// `id` matches the task keys in data/country_tasks.json.
// The 4 invisible-work items are not in ISSP (issp: false), so there are no
// country figures for them.

export const ANSWERS = [
  { value: "always_me", label: "Always me" },
  { value: "usually_me", label: "Usually me" },
  { value: "equal", label: "About equal or both together" },
  { value: "usually_partner", label: "Usually my partner" },
  { value: "always_partner", label: "Always my partner" },
  { value: "third_person", label: "Done by a third person" },
];

export const QUESTIONS = [
  { id: "laundry", text: "Doing the laundry", issp: true },
  { id: "plan_activities", text: "Planning social/family activities", issp: true },
  { id: "care_sick", text: "Caring for sick family members", issp: true },
  { id: "groceries", text: "Shopping for groceries", issp: true },
  { id: "cleaning", text: "Household cleaning", issp: true },
  { id: "meals", text: "Preparing meals", issp: true },
  { id: "birthdays_gifts", text: "Remembering birthdays and buying gifts", issp: false },
  { id: "noticing_supplies", text: "Noticing when supplies are running out", issp: false },
  { id: "booking_appointments", text: "Booking appointments", issp: false },
  { id: "tracking_schedules", text: "Keeping track of schedules", issp: false },
];
