"""WoW Forever references reviewed 2026-11-01.

IDs are Bluddit identifiers, not Blizzard IDs. Preserve them when replacing this
module with an external source. Suggested levels are guidance, not entry limits.
The nine new dungeon ranges follow Blizzard; remaining ranges/wings follow the
Icy Veins overview. Unpublished guide links are deliberately absent.
"""

import re

from bluddit_api.models.bluds import (
    BludReferenceData,
    Choice,
    ClassReference,
    DungeonReference,
    ProfessionReference,
    ReferenceSource,
)

DUNGEON_SOURCE = "https://www.icy-veins.com/wow-forever/dungeons-overview/"
BLIZZARD_DUNGEONS = "https://news.blizzard.com/en-gb/article/24301455/explore-the-new-dungeons-of-world-of-warcraft-forever"
PROFESSION_SOURCE = "https://news.blizzard.com/en-us/article/24301516/gather-around-the-campfire-in-world-of-warcraft-forever"
CLASS_SOURCE = "https://worldofwarcraft.blizzard.com/en-us/news/24304075/"
ZONE_SOURCE = "https://www.icy-veins.com/wow-forever/zones-and-maps"
QUEST_SOURCE = (
    "https://www.wowhead.com/forever/guide/dungeons/every-dungeon-quest-location"
)


def key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def choice(name: str) -> Choice:
    return Choice(id=key(name), name=name)


CLASSES = [
    ClassReference(
        id=key(name),
        name=name,
        specs=[Choice(id=f"{key(name)}-{key(spec)}", name=spec) for spec in specs],
    )
    for name, specs in [
        ("Druid", ["Balance", "Feral", "Restoration"]),
        ("Hunter", ["Beast Mastery", "Marksmanship", "Survival"]),
        ("Mage", ["Arcane", "Fire", "Frost"]),
        ("Paladin", ["Holy", "Protection", "Retribution"]),
        ("Priest", ["Discipline", "Holy", "Shadow"]),
        ("Rogue", ["Assassination", "Combat", "Subtlety"]),
        ("Shaman", ["Elemental", "Enhancement", "Restoration"]),
        ("Warlock", ["Affliction", "Demonology", "Destruction"]),
        ("Warrior", ["Arms", "Fury", "Protection"]),
    ]
]
PROFESSIONS = [
    ProfessionReference(id=key(name), name=name, category=category, max_level=300)
    for category, names in [
        (
            "primary",
            [
                "Alchemy",
                "Blacksmithing",
                "Enchanting",
                "Engineering",
                "Herbalism",
                "Leatherworking",
                "Mining",
                "Skinning",
                "Tailoring",
            ],
        ),
        ("secondary", ["Cooking", "First Aid", "Fishing"]),
    ]
    for name in names
]
# Outdoor Classic zones plus the four Forever additions. Cities are valid farming
# locations too (e.g. fishing). No Retail expansion zones or guessed level gates.
ZONES = [
    choice(name)
    for name in sorted(
        [
            "Alterac Mountains",
            "Arathi Highlands",
            "Ashenvale",
            "Azshara",
            "Badlands",
            "Blasted Lands",
            "Burning Steppes",
            "Darkshore",
            "Darnassus",
            "Deadwind Pass",
            "Desolace",
            "Dun Morogh",
            "Durotar",
            "Duskwood",
            "Dustwallow Marsh",
            "Eastern Plaguelands",
            "Elwynn Forest",
            "Felwood",
            "Feralas",
            "Hillsbrad Foothills",
            "Ironforge",
            "Loch Modan",
            "Moonglade",
            "Mount Hyjal",
            "Mulgore",
            "Orgrimmar",
            "Redridge Mountains",
            "Riverglades",
            "Searing Gorge",
            "Shen'Dralas",
            "Silithus",
            "Silverpine Forest",
            "Stonetalon Mountains",
            "Stormwind",
            "Stranglethorn Vale",
            "Swamp of Sorrows",
            "Tanaris",
            "Teldrassil",
            "The Barrens",
            "The Hinterlands",
            "Thousand Needles",
            "Thunder Bluff",
            "Tirisfal Glades",
            "Un'Goro Crater",
            "Undercity",
            "Western Plaguelands",
            "Westfall",
            "Wetlands",
            "Winterspring",
            "Zephras Isle",
        ]
    )
]
# Stable ID, display name, suggested min/max, location, available guide stem,
# whether Blizzard publishes the new dungeon's range.
_DUNGEONS = [
    ("ragefire-chasm", "Ragefire Chasm", 13, 18, "Orgrimmar", "ragefire-chasm", False),
    ("hall-of-thanes", "Hall of Thanes", 13, 18, "Dun Morogh", "hall-of-thanes", True),
    (
        "ruins-of-lordaeron",
        "Ruins of Lordaeron",
        15,
        20,
        "Tirisfal Glades",
        "ruins-of-lordaeron",
        True,
    ),
    (
        "wailing-caverns",
        "Wailing Caverns",
        15,
        24,
        "The Barrens",
        "wailing-caverns",
        False,
    ),
    ("deadmines", "Deadmines", 17, 26, "Westfall", "deadmines", False),
    (
        "shadowfang-keep",
        "Shadowfang Keep",
        20,
        30,
        "Silverpine Forest",
        "shadowfang-keep",
        False,
    ),
    (
        "blackfathom-deeps",
        "Blackfathom Deeps",
        24,
        32,
        "Ashenvale",
        "blackfathom-deeps",
        False,
    ),
    (
        "stormwind-stockades",
        "Stormwind Stockades",
        24,
        32,
        "Stormwind",
        "the-stockade",
        False,
    ),
    (
        "excavation-site",
        "Excavation Site: Wetlands",
        24,
        29,
        "Wetlands",
        "excavation-site-wetlands",
        True,
    ),
    (
        "city-of-dalaran",
        "City of Dalaran",
        28,
        33,
        "Alterac Mountains",
        "city-of-dalaran",
        True,
    ),
    ("gnomeregan", "Gnomeregan", 29, 38, "Dun Morogh", "gnomeregan", False),
    (
        "razorfen-kraul",
        "Razorfen Kraul",
        29,
        38,
        "The Barrens",
        "razorfen-kraul",
        False,
    ),
    (
        "scarlet-monastery-graveyard",
        "Scarlet Monastery - Graveyard",
        30,
        38,
        "Tirisfal Glades",
        "scarlet-monastery-graveyard",
        False,
    ),
    (
        "scarlet-monastery-library",
        "Scarlet Monastery - Library",
        33,
        41,
        "Tirisfal Glades",
        "scarlet-monastery-library",
        False,
    ),
    ("drowned-city", "The Drowned City", 35, 40, "Stranglethorn Vale", None, True),
    (
        "scarlet-monastery-armory",
        "Scarlet Monastery - Armory",
        36,
        44,
        "Tirisfal Glades",
        None,
        False,
    ),
    ("razorfen-downs", "Razorfen Downs", 37, 46, "Thousand Needles", None, False),
    (
        "scarlet-monastery-cathedral",
        "Scarlet Monastery - Cathedral",
        38,
        46,
        "Tirisfal Glades",
        None,
        False,
    ),
    ("krol-dok-stronghold", "Krol'dok Stronghold", 40, 45, "Riverglades", None, True),
    ("uldaman", "Uldaman", 41, 51, "Badlands", None, False),
    ("zul-farrak", "Zul'Farrak", 44, 54, "Tanaris", None, False),
    ("maraudon", "Maraudon", 46, 55, "Desolace", None, False),
    ("alcaz-prison", "Alcaz Prison", 48, 53, "Dustwallow Marsh", None, True),
    ("sunken-temple", "Sunken Temple", 50, 60, "Swamp of Sorrows", None, False),
    ("blackrock-depths", "Blackrock Depths", 52, 60, "Blackrock Mountain", None, False),
    ("dire-maul-east", "Dire Maul (East)", 54, 60, "Feralas", None, False),
    ("blackmaw-hold", "Blackmaw Hold", 55, 60, "Azshara", None, True),
    (
        "lower-blackrock-spire",
        "Lower Blackrock Spire",
        55,
        60,
        "Blackrock Mountain",
        None,
        False,
    ),
    ("dire-maul-north", "Dire Maul (North)", 56, 60, "Feralas", None, False),
    ("dire-maul-west", "Dire Maul (West)", 56, 60, "Feralas", None, False),
    ("scholomance", "Scholomance", 58, 60, "Western Plaguelands", None, False),
    ("shapers-terrace", "Shaper's Terrace", 58, 60, "Un'Goro Crater", None, True),
    (
        "stratholme-main-gate",
        "Stratholme (Main Gate)",
        58,
        60,
        "Eastern Plaguelands",
        None,
        False,
    ),
    (
        "stratholme-service-gate",
        "Stratholme (Service Gate)",
        58,
        60,
        "Eastern Plaguelands",
        None,
        False,
    ),
    (
        "upper-blackrock-spire",
        "Upper Blackrock Spire",
        59,
        60,
        "Blackrock Mountain",
        None,
        False,
    ),
]
DUNGEONS = [
    DungeonReference(
        id=identifier,
        name=name,
        suggested_level_min=low,
        suggested_level_max=high,
        location=location,
        guide_url=f"https://www.icy-veins.com/wow-forever/{stem}-guide"
        if stem
        else None,
        quest_guide_url=f"https://www.icy-veins.com/wow-forever/{stem}-quests"
        if stem
        else None,
        source_urls=[BLIZZARD_DUNGEONS if official else DUNGEON_SOURCE],
    )
    for identifier, name, low, high, location, stem, official in _DUNGEONS
]
REFERENCES = BludReferenceData(
    version="2026-11-01.1",
    reviewed_on="2026-11-01",
    sources=[
        ReferenceSource(label=label, url=url)
        for label, url in [
            ("Blizzard: new dungeon ranges", BLIZZARD_DUNGEONS),
            ("Icy Veins: dungeon checklist and class/spec guides", DUNGEON_SOURCE),
            ("Blizzard: classes", CLASS_SOURCE),
            ("Blizzard: profession categories", PROFESSION_SOURCE),
            (
                "Icy Veins: profession skill caps",
                "https://www.icy-veins.com/wow-forever/professions-overview",
            ),
            ("Icy Veins: Forever zones", ZONE_SOURCE),
            (
                "Wowhead: dungeon quests (beta / Classic-derived entries marked)",
                QUEST_SOURCE,
            ),
        ]
    ],
    classes=CLASSES,
    professions=PROFESSIONS,
    zones=ZONES,
    dungeons=DUNGEONS,
    max_primary_professions=2,
    dungeon_statuses=[
        Choice(id="not_completed", name="Not completed"),
        Choice(id="completed", name="Completed"),
        Choice(id="completed_rerun", name="Completed — looking to rerun"),
    ],
)
CLASS_BY_ID = {item.id: item for item in CLASSES}
PROFESSION_BY_ID = {item.id: item for item in PROFESSIONS}
ZONE_IDS = {item.id for item in ZONES}
DUNGEON_IDS = {item.id for item in DUNGEONS}
