"""Idempotent seed data for local/dev Postgres — 36 realistic complaints in
Urdu-influenced English, spread across every category/priority/status value
the schema defines.

Not an Alembic migration — migrations stay schema-only (CONTRACTS.md §2.3).

Run with:
    python -m app.scripts.seed

Idempotency: each row's primary key is `uuid.uuid5(uuid.NAMESPACE_URL, ...)`
derived deterministically from the complaint text, so the same seed content
always maps to the same `id`. Insert uses `ON CONFLICT (id) DO NOTHING`, so
running this script any number of times leaves exactly the same rows.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db import engine

# (text, location, reporter_contact, category, priority, status,
#  ai_summary, triaged_by, triage_latency_ms, days_ago)
_COMPLAINTS: list[tuple[str, str, str | None, str, str, str, str, str, int, int]] = [
    # -- water --
    ("Water supply is completely stopped in our gali since last three days, "
     "kindly resolve on urgent basis.", "Gulshan-e-Iqbal, Block 5, Karachi",
     "0301-2345671", "water", "high", "open",
     "No water supply for 3 days in residential block", "llm:gemini", 850, 1),
    ("Drinking water is very dirty and smells bad, whole mohalla is facing "
     "this since one week.", "Model Colony, Malir", None,
     "water", "high", "in_progress",
     "Contaminated drinking water reported in colony", "llm:gemini", 910, 5),
    ("Water pressure is very low in our area from many days, tank is not "
     "filling properly.", "North Nazimabad, Block C", "0333-4455667",
     "water", "normal", "open",
     "Persistently low water pressure in block", "rules", 60, 2),
    ("There is water leakage from main pipeline near the park, water is "
     "being wasted daily.", "Askari Park Road, Rawalpindi", None,
     "water", "normal", "resolved",
     "Main pipeline leakage wasting water near park", "llm:gemini", 780, 12),
    ("Water tanker is not coming on time as per schedule, please look into "
     "this matter.", "Shah Faisal Colony No. 3", "0321-9988776",
     "water", "low", "open",
     "Water tanker delivery delayed against schedule", "rules", 45, 3),
    ("Water line got mixed with sewerage line, very unhygienic condition "
     "for whole street.", "Liaquatabad No. 10", None,
     "water", "high", "in_progress",
     "Water line contaminated by sewerage crossover", "llm:gemini", 990, 4),
    # -- electricity --
    ("Electricity is going on and off since morning, transformer seems "
     "faulty.", "Wapda Town, Phase 1, Lahore", "0300-1122334",
     "electricity", "high", "open",
     "Frequent power outages, suspected faulty transformer", "llm:gemini", 870, 1),
    ("No light in our street from two days, please send lineman as soon as "
     "possible.", "Samanabad, Block A", None,
     "electricity", "high", "in_progress",
     "Street without electricity for two days", "rules", 55, 6),
    ("Voltage fluctuation is damaging our home appliances since many "
     "weeks.", "Faisal Town, Block D", "0345-6677889",
     "electricity", "normal", "open",
     "Voltage fluctuation damaging household appliances", "llm:gemini", 820, 8),
    ("Electricity pole is leaning dangerously after the storm, kindly do "
     "the needful.", "Township, Sector B", None,
     "electricity", "high", "resolved",
     "Leaning electricity pole poses safety hazard", "llm:gemini", 940, 15),
    ("Meter reading is wrong from last two months, bill is coming very "
     "high.", "Garden Town, Block 2", "0312-3344556",
     "electricity", "low", "rejected",
     "Dispute over incorrect meter reading and billing", "rules:fallback", 40, 20),
    ("Underground cable is exposed near the school, children are playing "
     "nearby, very risky.", "Johar Town, Phase 2", None,
     "electricity", "high", "in_progress",
     "Exposed underground cable near school poses risk", "llm:gemini", 960, 2),
    # -- sanitation --
    ("Sewerage line is overflow near the mosque since many days, very bad "
     "smell in whole area.", "Shahdara, Main Bazaar", "0334-5566778",
     "sanitation", "high", "open",
     "Overflowing sewerage line causing bad smell near mosque", "llm:gemini", 880, 2),
    ("Garbage is not collected from many days, whole street is filled with "
     "trash.", "Korangi No. 6", None,
     "sanitation", "normal", "in_progress",
     "No garbage collection for several days on street", "rules", 50, 4),
    ("Manhole cover is missing outside our house, very dangerous especially "
     "for children.", "Nazimabad No. 3", "0302-7788990",
     "sanitation", "high", "resolved",
     "Missing manhole cover creates safety hazard", "llm:gemini", 900, 18),
    ("Drain is blocked due to plastic waste, water is standing on road "
     "after every rain.", "PECHS Block 6", None,
     "sanitation", "normal", "open",
     "Blocked drain causing standing water after rain", "rules", 58, 1),
    ("Public toilet near the bus stop is in very bad condition, no water "
     "and very dirty.", "Saddar, Regal Chowk", "0341-2233445",
     "sanitation", "low", "rejected",
     "Public toilet reported unhygienic and lacking water", "rules:fallback", 42, 25),
    ("Dead animal is lying on the roadside from two days, kindly remove it "
     "urgently.", "Landhi No. 4", None,
     "sanitation", "high", "in_progress",
     "Dead animal on roadside needs urgent removal", "llm:gemini", 930, 1),
    # -- roads --
    ("Road has many potholes, one bike accident already happened near the "
     "chowk.", "Main Boulevard, DHA Phase 6", "0308-9900112",
     "roads", "high", "open",
     "Multiple potholes causing accidents on boulevard", "llm:gemini", 870, 3),
    ("Road is completely damaged after the rain, very difficult for "
     "rickshaws to pass.", "Baldia Town, Sector 5", None,
     "roads", "normal", "in_progress",
     "Rain damage leaves road difficult to traverse", "rules", 62, 7),
    ("Speed breaker is not visible at night, no paint, causing accidents.",
     "University Road, Peshawar", "0315-6677001",
     "roads", "high", "open",
     "Unmarked speed breaker causing night accidents", "llm:gemini", 910, 2),
    ("Construction debris is lying on the road since many weeks, blocking "
     "half the road.", "Clifton Block 4", None,
     "roads", "normal", "resolved",
     "Construction debris blocking road for weeks", "llm:gemini", 850, 14),
    ("Footpath is broken outside the school, students have to walk on the "
     "road.", "Anarkali, Lahore", "0322-4455998",
     "roads", "high", "in_progress",
     "Broken footpath forces students onto road", "llm:gemini", 920, 5),
    ("Road markings have faded completely, very confusing for drivers at "
     "night.", "Shahrah-e-Faisal", None,
     "roads", "low", "open",
     "Faded road markings create driving confusion", "rules", 47, 9),
    # -- streetlights --
    ("Streetlight is closed from last one week, whole gali is dark at "
     "night, girls feel unsafe.", "Gulberg, Block 3", "0333-1122998",
     "streetlights", "high", "open",
     "Non-functional streetlight leaves lane dark and unsafe", "llm:gemini", 890, 1),
    ("Two streetlights are flickering continuously since many days near "
     "the park.", "Iqbal Town, Block P", None,
     "streetlights", "low", "in_progress",
     "Flickering streetlights reported near park", "rules", 44, 6),
    ("Streetlight pole is broken and hanging, please fix before it falls "
     "on someone.", "Defence Phase 4", "0345-8899001",
     "streetlights", "high", "resolved",
     "Broken hanging streetlight pole poses danger", "llm:gemini", 970, 16),
    ("No streetlights at all in our new housing scheme since it was built, "
     "very dark.", "Bahria Town, Sector C", None,
     "streetlights", "normal", "open",
     "New housing scheme entirely lacks streetlights", "llm:gemini", 860, 4),
    ("Streetlight wiring is exposed after storm, could be dangerous in "
     "rain.", "Cantt Area, Multan", "0301-5566223",
     "streetlights", "high", "in_progress",
     "Exposed streetlight wiring hazardous during rain", "llm:gemini", 940, 2),
    ("Streetlight timer is not working, lights remain on even in daytime, "
     "wasting electricity.", "Satellite Town, Rawalpindi", None,
     "streetlights", "low", "rejected",
     "Malfunctioning streetlight timer wastes electricity", "rules:fallback", 39, 22),
    # -- other --
    ("Stray dogs are increasing in our area, already two people got bitten "
     "this month.", "Gizri, Karachi", "0312-6677889",
     "other", "high", "open",
     "Rise in stray dog attacks reported in area", "llm:gemini", 900, 2),
    ("Noise pollution from wedding halls continues till very late night, "
     "please take action.", "Cavalry Ground, Lahore", None,
     "other", "normal", "in_progress",
     "Wedding halls causing late-night noise pollution", "rules", 53, 5),
    ("Illegal encroachment on footpath by shopkeepers, pedestrians forced "
     "onto busy road.", "Tariq Road, Karachi", "0300-8899776",
     "other", "normal", "open",
     "Illegal footpath encroachment forces pedestrians onto road", "llm:gemini", 830, 3),
    ("Public park is being used as garbage dumping point, kindly install "
     "proper bins.", "F-10 Park, Islamabad", None,
     "other", "low", "resolved",
     "Park misused as dumping site, bins requested", "llm:gemini", 800, 20),
    ("Illegal parking outside the market is causing traffic jam every "
     "evening.", "Urdu Bazaar, Lahore", "0321-1234598",
     "other", "normal", "in_progress",
     "Illegal market parking causing evening traffic jams", "rules", 57, 4),
    ("Mobile tower signal is interfering with our TV cable connection "
     "since installation.", "Askari 11, Lahore", None,
     "other", "low", "open",
     "Mobile tower reportedly interfering with cable TV", "rules", 48, 6),
]

_INSERT = text(
    """
    INSERT INTO complaints (
        id, text, location, reporter_contact, category, priority, status,
        ai_summary, triaged_by, triage_latency_ms, created_at, updated_at
    ) VALUES (
        :id, :text, :location, :reporter_contact, :category, :priority, :status,
        :ai_summary, :triaged_by, :triage_latency_ms, :created_at, :updated_at
    )
    ON CONFLICT (id) DO NOTHING
    """
)


def _row_params(
    complaint: tuple[str, str, str | None, str, str, str, str, str, int, int],
) -> dict[str, object]:
    (
        complaint_text, location, reporter_contact, category, priority,
        status, ai_summary, triaged_by, triage_latency_ms, days_ago,
    ) = complaint
    complaint_id = uuid.uuid5(uuid.NAMESPACE_URL, f"civicpulse:seed:{complaint_text}")
    created_at = datetime.now(UTC) - timedelta(days=days_ago)
    updated_at = created_at if status == "open" else created_at + timedelta(hours=6)
    return {
        "id": complaint_id,
        "text": complaint_text,
        "location": location,
        "reporter_contact": reporter_contact,
        "category": category,
        "priority": priority,
        "status": status,
        "ai_summary": ai_summary,
        "triaged_by": triaged_by,
        "triage_latency_ms": triage_latency_ms,
        "created_at": created_at,
        "updated_at": updated_at,
    }


async def seed() -> int:
    """Insert all seed complaints. Returns the count actually inserted this run."""
    inserted = 0
    async with engine.begin() as conn:
        for complaint in _COMPLAINTS:
            result = await conn.execute(_INSERT, _row_params(complaint))
            inserted += result.rowcount
    return inserted


async def main() -> None:
    inserted = await seed()
    skipped = len(_COMPLAINTS) - inserted
    print(f"Seed complete: {inserted} new row(s) inserted, {skipped} already present.")


if __name__ == "__main__":
    asyncio.run(main())
