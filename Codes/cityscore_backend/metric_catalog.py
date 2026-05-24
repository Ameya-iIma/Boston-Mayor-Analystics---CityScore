from __future__ import annotations

from collections.abc import Iterable


METRIC_ALIASES = {
    "311 CONSTITUENT EXPERIENCE SURVEYS": "CITY SERVICES SATISFACTION SURVEYS",
    "CONSTITUENT SATISFACTION SURVEYS": "CITY SERVICES SATISFACTION SURVEYS",
    "GRAFFITI REMOVAL ON-TIME %": "GRAFFITI ON-TIME %",
    "MISSED TRASH ON-TIME %": "MISSED TRASH ON-TIME %",
    "POTHOLE REPAIR ON-TIME %": "POTHOLE ON-TIME %",
}


METRIC_CATALOG = {
    "311 CALL CENTER PERFORMANCE": {
        "display_name": "311 Call Center Performance",
        "service_area": "Resident Experience",
        "owner_department": "311 Constituent Services",
        "cadence": "weekday",
        "definition": "Percent of 311 calls answered within 30 seconds against a 95% goal.",
    },
    "CITY SERVICES SATISFACTION SURVEYS": {
        "display_name": "City Services Satisfaction Surveys",
        "service_area": "Resident Experience",
        "owner_department": "311 Constituent Services",
        "cadence": "sparse",
        "definition": "Average resident satisfaction score from constituent surveys with a goal of 4 out of 5.",
    },
    "BFD INCIDENTS": {
        "display_name": "BFD Incidents",
        "service_area": "Public Safety",
        "owner_department": "Boston Fire Department",
        "cadence": "weekday",
        "definition": "Fire-related incidents versus the historical average. Scores above 1 indicate fewer incidents.",
    },
    "BFD RESPONSE TIME": {
        "display_name": "BFD Response Time",
        "service_area": "Public Safety",
        "owner_department": "Boston Fire Department",
        "cadence": "weekday",
        "definition": "Percent of fire responses arriving within 4 minutes from station departure against a 90% goal.",
    },
    "BPS ATTENDANCE": {
        "display_name": "BPS Attendance",
        "service_area": "Education And Civic Life",
        "owner_department": "Boston Public Schools",
        "cadence": "school_day",
        "definition": "Student attendance rate across Boston Public Schools against a 95% goal.",
    },
    "CODE ENFORCEMENT ON-TIME %": {
        "display_name": "Code Enforcement On-Time %",
        "service_area": "Permits And Code",
        "owner_department": "Inspectional Services",
        "cadence": "weekday",
        "definition": "On-time completion score for code enforcement requests.",
    },
    "CODE ENFORCEMENT TRASH COLLECTION": {
        "display_name": "Code Enforcement Trash Collection",
        "service_area": "Permits And Code",
        "owner_department": "Inspectional Services",
        "cadence": "weekday",
        "definition": "Operational score tied to code enforcement trash collection activity.",
    },
    "EMS INCIDENTS": {
        "display_name": "EMS Incidents",
        "service_area": "Public Safety",
        "owner_department": "Emergency Medical Services",
        "cadence": "weekday",
        "definition": "EMS incident volume versus the historical average. Scores above 1 indicate fewer incidents.",
    },
    "EMS RESPONSE TIME": {
        "display_name": "EMS Response Time",
        "service_area": "Public Safety",
        "owner_department": "Emergency Medical Services",
        "cadence": "weekday",
        "definition": "Median priority-1 EMS response time against a 6-minute goal.",
    },
    "GRAFFITI ON-TIME %": {
        "display_name": "Graffiti Removal On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Public Works",
        "cadence": "weekday",
        "definition": "Percent of graffiti requests completed within the service target.",
    },
    "HOMICIDES (TREND)": {
        "display_name": "Homicides",
        "service_area": "Public Safety",
        "owner_department": "Boston Police Department",
        "cadence": "weekday",
        "definition": "Homicide trend versus historical average. Scores above 1 indicate fewer homicides.",
    },
    "LIBRARY USERS": {
        "display_name": "Library Users",
        "service_area": "Education And Civic Life",
        "owner_department": "Boston Public Library",
        "cadence": "weekday",
        "definition": "Active Boston Public Library users versus the historical average. Scores above 1 indicate growth.",
    },
    "MISSED TRASH ON-TIME %": {
        "display_name": "Missed Trash On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Public Works",
        "cadence": "weekday",
        "definition": "Percent of missed trash requests inspected within one business day.",
    },
    "ON-TIME PERMIT REVIEWS": {
        "display_name": "On-Time Permit Reviews",
        "service_area": "Permits And Code",
        "owner_department": "Planning And Development",
        "cadence": "weekday",
        "definition": "Percent of as-of-right permits reviewed within 20 business days.",
    },
    "PARKS MAINTENANCE ON-TIME %": {
        "display_name": "Parks Maintenance On-Time %",
        "service_area": "Parks And Public Realm",
        "owner_department": "Parks And Recreation",
        "cadence": "weekday",
        "definition": "Percent of parks maintenance requests completed within the service target.",
    },
    "PART 1 CRIMES": {
        "display_name": "Part 1 Crimes",
        "service_area": "Public Safety",
        "owner_department": "Boston Police Department",
        "cadence": "weekday",
        "definition": "Serious FBI index crimes excluding homicides, shootings, and stabbings. Scores above 1 indicate fewer crimes.",
    },
    "POTHOLE ON-TIME %": {
        "display_name": "Pothole Repair On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Public Works",
        "cadence": "weekday",
        "definition": "Percent of potholes repaired within one business day.",
    },
    "SHOOTINGS (TREND)": {
        "display_name": "Shootings",
        "service_area": "Public Safety",
        "owner_department": "Boston Police Department",
        "cadence": "weekday",
        "definition": "Non-fatal shootings versus the historical average. Scores above 1 indicate fewer shootings.",
    },
    "SIGN INSTALLATION ON-TIME %": {
        "display_name": "Sign Installation On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Transportation",
        "cadence": "weekday",
        "definition": "Percent of approved sign installations completed within 30 calendar days.",
    },
    "SIGNAL REPAIR ON-TIME %": {
        "display_name": "Signal Repair On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Transportation",
        "cadence": "weekday",
        "definition": "Percent of traffic signal outages repaired within 24 hours.",
    },
    "STABBINGS (TREND)": {
        "display_name": "Stabbings",
        "service_area": "Public Safety",
        "owner_department": "Boston Police Department",
        "cadence": "weekday",
        "definition": "Non-fatal stabbings versus the historical average. Scores above 1 indicate fewer stabbings.",
    },
    "STREETLIGHT ON-TIME %": {
        "display_name": "Streetlight On-Time %",
        "service_area": "Streets And Public Works",
        "owner_department": "Public Works",
        "cadence": "weekday",
        "definition": "Percent of streetlight repair requests completed within the service target.",
    },
    "TREE MAINTENANCE ON-TIME %": {
        "display_name": "Tree Maintenance On-Time %",
        "service_area": "Parks And Public Realm",
        "owner_department": "Parks And Recreation",
        "cadence": "weekday",
        "definition": "Percent of tree maintenance requests completed within the service target.",
    },
}


SERVICE_AREA_ORDER = [
    "Public Safety",
    "Resident Experience",
    "Streets And Public Works",
    "Parks And Public Realm",
    "Permits And Code",
    "Education And Civic Life",
    "Unassigned",
]


def normalize_metric_name(metric_name: str | None) -> str:
    if metric_name is None:
        return "UNKNOWN METRIC"
    cleaned_name = " ".join(str(metric_name).strip().upper().split())
    if cleaned_name in {"", "<NA>", "NAN", "NONE"}:
        return "UNKNOWN METRIC"
    return METRIC_ALIASES.get(cleaned_name, cleaned_name)


def get_metric_metadata(metric_name: str | None) -> dict[str, str]:
    canonical_name = normalize_metric_name(metric_name)
    base = {
        "metric_name": canonical_name,
        "display_name": canonical_name.title(),
        "service_area": "Unassigned",
        "owner_department": "Unassigned",
        "cadence": "unknown",
        "definition": "Definition not yet mapped from the CityScore metric catalog.",
    }
    return {**base, **METRIC_CATALOG.get(canonical_name, {})}


def list_service_areas(metrics: Iterable[str]) -> list[str]:
    seen = {get_metric_metadata(metric)["service_area"] for metric in metrics}
    ordered = [service_area for service_area in SERVICE_AREA_ORDER if service_area in seen]
    leftovers = sorted(seen.difference(ordered))
    return ordered + leftovers
