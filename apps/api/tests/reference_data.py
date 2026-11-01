"""Synthetic catalog for workflow tests; never imported by the application."""

from bluddit_api.models.bluds import (
    BludReferenceData,
    Choice,
    ClassReference,
    ProfessionReference,
    DungeonReference,
)

REFERENCES = BludReferenceData(
    version="synthetic-1",
    sources=[],
    max_primary_professions=2,
    classes=[
        ClassReference(
            id="druid",
            name="Druid",
            specs=[
                {"id": "druid-balance", "name": "Balance"},
                {"id": "druid-feral", "name": "Feral"},
                {"id": "druid-restoration", "name": "Restoration"},
            ],
        ),
        ClassReference(
            id="hunter",
            name="Hunter",
            specs=[
                {"id": "hunter-beast-mastery", "name": "Beast Mastery"},
                {"id": "hunter-marksmanship", "name": "Marksmanship"},
                {"id": "hunter-survival", "name": "Survival"},
            ],
        ),
        ClassReference(
            id="mage",
            name="Mage",
            specs=[
                {"id": "mage-arcane", "name": "Arcane"},
                {"id": "mage-fire", "name": "Fire"},
                {"id": "mage-frost", "name": "Frost"},
            ],
        ),
        ClassReference(
            id="paladin",
            name="Paladin",
            specs=[
                {"id": "paladin-holy", "name": "Holy"},
                {"id": "paladin-protection", "name": "Protection"},
                {"id": "paladin-retribution", "name": "Retribution"},
            ],
        ),
        ClassReference(
            id="priest",
            name="Priest",
            specs=[
                {"id": "priest-discipline", "name": "Discipline"},
                {"id": "priest-holy", "name": "Holy"},
                {"id": "priest-shadow", "name": "Shadow"},
            ],
        ),
        ClassReference(
            id="rogue",
            name="Rogue",
            specs=[
                {"id": "rogue-assassination", "name": "Assassination"},
                {"id": "rogue-combat", "name": "Combat"},
                {"id": "rogue-subtlety", "name": "Subtlety"},
            ],
        ),
        ClassReference(
            id="shaman",
            name="Shaman",
            specs=[
                {"id": "shaman-elemental", "name": "Elemental"},
                {"id": "shaman-enhancement", "name": "Enhancement"},
                {"id": "shaman-restoration", "name": "Restoration"},
            ],
        ),
        ClassReference(
            id="warlock",
            name="Warlock",
            specs=[
                {"id": "warlock-affliction", "name": "Affliction"},
                {"id": "warlock-demonology", "name": "Demonology"},
                {"id": "warlock-destruction", "name": "Destruction"},
            ],
        ),
        ClassReference(
            id="warrior",
            name="Warrior",
            specs=[
                {"id": "warrior-arms", "name": "Arms"},
                {"id": "warrior-fury", "name": "Fury"},
                {"id": "warrior-protection", "name": "Protection"},
            ],
        ),
    ],
    professions=[
        ProfessionReference(
            id="alchemy", name="Alchemy", category="primary", max_level=300
        ),
        ProfessionReference(
            id="blacksmithing", name="Blacksmithing", category="primary", max_level=300
        ),
        ProfessionReference(
            id="enchanting", name="Enchanting", category="primary", max_level=300
        ),
        ProfessionReference(
            id="engineering", name="Engineering", category="primary", max_level=300
        ),
        ProfessionReference(
            id="herbalism", name="Herbalism", category="primary", max_level=300
        ),
        ProfessionReference(
            id="leatherworking",
            name="Leatherworking",
            category="primary",
            max_level=300,
        ),
        ProfessionReference(
            id="mining", name="Mining", category="primary", max_level=300
        ),
        ProfessionReference(
            id="skinning", name="Skinning", category="primary", max_level=300
        ),
        ProfessionReference(
            id="tailoring", name="Tailoring", category="primary", max_level=300
        ),
        ProfessionReference(
            id="cooking", name="Cooking", category="secondary", max_level=300
        ),
        ProfessionReference(
            id="first-aid", name="First Aid", category="secondary", max_level=300
        ),
        ProfessionReference(
            id="fishing", name="Fishing", category="secondary", max_level=300
        ),
    ],
    dungeons=[
        DungeonReference(
            id="ragefire-chasm",
            name="Ragefire Chasm",
            suggested_level_min=13,
            suggested_level_max=18,
            location="Orgrimmar",
        ),
        DungeonReference(
            id="hall-of-thanes",
            name="Hall of Thanes",
            suggested_level_min=13,
            suggested_level_max=18,
            location="Dun Morogh",
        ),
        DungeonReference(
            id="ruins-of-lordaeron",
            name="Ruins of Lordaeron",
            suggested_level_min=15,
            suggested_level_max=20,
            location="Tirisfal Glades",
        ),
        DungeonReference(
            id="wailing-caverns",
            name="Wailing Caverns",
            suggested_level_min=15,
            suggested_level_max=24,
            location="The Barrens",
        ),
        DungeonReference(
            id="deadmines",
            name="Deadmines",
            suggested_level_min=17,
            suggested_level_max=26,
            location="Westfall",
        ),
        DungeonReference(
            id="shadowfang-keep",
            name="Shadowfang Keep",
            suggested_level_min=20,
            suggested_level_max=30,
            location="Silverpine Forest",
        ),
        DungeonReference(
            id="blackfathom-deeps",
            name="Blackfathom Deeps",
            suggested_level_min=24,
            suggested_level_max=32,
            location="Ashenvale",
        ),
        DungeonReference(
            id="stormwind-stockades",
            name="Stormwind Stockades",
            suggested_level_min=24,
            suggested_level_max=32,
            location="Stormwind",
        ),
        DungeonReference(
            id="excavation-site",
            name="Excavation Site: Wetlands",
            suggested_level_min=24,
            suggested_level_max=29,
            location="Wetlands",
        ),
        DungeonReference(
            id="city-of-dalaran",
            name="City of Dalaran",
            suggested_level_min=28,
            suggested_level_max=33,
            location="Alterac Mountains",
        ),
        DungeonReference(
            id="gnomeregan",
            name="Gnomeregan",
            suggested_level_min=29,
            suggested_level_max=38,
            location="Dun Morogh",
        ),
        DungeonReference(
            id="razorfen-kraul",
            name="Razorfen Kraul",
            suggested_level_min=29,
            suggested_level_max=38,
            location="The Barrens",
        ),
        DungeonReference(
            id="scarlet-monastery-graveyard",
            name="Scarlet Monastery - Graveyard",
            suggested_level_min=30,
            suggested_level_max=38,
            location="Tirisfal Glades",
        ),
        DungeonReference(
            id="scarlet-monastery-library",
            name="Scarlet Monastery - Library",
            suggested_level_min=33,
            suggested_level_max=41,
            location="Tirisfal Glades",
        ),
        DungeonReference(
            id="drowned-city",
            name="The Drowned City",
            suggested_level_min=35,
            suggested_level_max=40,
            location="Stranglethorn Vale",
        ),
        DungeonReference(
            id="scarlet-monastery-armory",
            name="Scarlet Monastery - Armory",
            suggested_level_min=36,
            suggested_level_max=44,
            location="Tirisfal Glades",
        ),
        DungeonReference(
            id="razorfen-downs",
            name="Razorfen Downs",
            suggested_level_min=37,
            suggested_level_max=46,
            location="Thousand Needles",
        ),
        DungeonReference(
            id="scarlet-monastery-cathedral",
            name="Scarlet Monastery - Cathedral",
            suggested_level_min=38,
            suggested_level_max=46,
            location="Tirisfal Glades",
        ),
        DungeonReference(
            id="krol-dok-stronghold",
            name="Krol'dok Stronghold",
            suggested_level_min=40,
            suggested_level_max=45,
            location="Riverglades",
        ),
        DungeonReference(
            id="uldaman",
            name="Uldaman",
            suggested_level_min=41,
            suggested_level_max=51,
            location="Badlands",
        ),
        DungeonReference(
            id="zul-farrak",
            name="Zul'Farrak",
            suggested_level_min=44,
            suggested_level_max=54,
            location="Tanaris",
        ),
        DungeonReference(
            id="maraudon",
            name="Maraudon",
            suggested_level_min=46,
            suggested_level_max=55,
            location="Desolace",
        ),
        DungeonReference(
            id="alcaz-prison",
            name="Alcaz Prison",
            suggested_level_min=48,
            suggested_level_max=53,
            location="Dustwallow Marsh",
        ),
        DungeonReference(
            id="sunken-temple",
            name="Sunken Temple",
            suggested_level_min=50,
            suggested_level_max=60,
            location="Swamp of Sorrows",
        ),
        DungeonReference(
            id="blackrock-depths",
            name="Blackrock Depths",
            suggested_level_min=52,
            suggested_level_max=60,
            location="Blackrock Mountain",
        ),
        DungeonReference(
            id="dire-maul-east",
            name="Dire Maul (East)",
            suggested_level_min=54,
            suggested_level_max=60,
            location="Feralas",
        ),
        DungeonReference(
            id="blackmaw-hold",
            name="Blackmaw Hold",
            suggested_level_min=55,
            suggested_level_max=60,
            location="Azshara",
        ),
        DungeonReference(
            id="lower-blackrock-spire",
            name="Lower Blackrock Spire",
            suggested_level_min=55,
            suggested_level_max=60,
            location="Blackrock Mountain",
        ),
        DungeonReference(
            id="dire-maul-north",
            name="Dire Maul (North)",
            suggested_level_min=56,
            suggested_level_max=60,
            location="Feralas",
        ),
        DungeonReference(
            id="dire-maul-west",
            name="Dire Maul (West)",
            suggested_level_min=56,
            suggested_level_max=60,
            location="Feralas",
        ),
        DungeonReference(
            id="scholomance",
            name="Scholomance",
            suggested_level_min=58,
            suggested_level_max=60,
            location="Western Plaguelands",
        ),
        DungeonReference(
            id="shapers-terrace",
            name="Shaper's Terrace",
            suggested_level_min=58,
            suggested_level_max=60,
            location="Un'Goro Crater",
        ),
        DungeonReference(
            id="stratholme-main-gate",
            name="Stratholme (Main Gate)",
            suggested_level_min=58,
            suggested_level_max=60,
            location="Eastern Plaguelands",
        ),
        DungeonReference(
            id="stratholme-service-gate",
            name="Stratholme (Service Gate)",
            suggested_level_min=58,
            suggested_level_max=60,
            location="Eastern Plaguelands",
        ),
        DungeonReference(
            id="upper-blackrock-spire",
            name="Upper Blackrock Spire",
            suggested_level_min=59,
            suggested_level_max=60,
            location="Blackrock Mountain",
        ),
    ],
    dungeon_statuses=[
        Choice(id="not_completed", name="Not completed"),
        Choice(id="completed", name="Completed"),
        Choice(id="completed_rerun", name="Completed — looking to rerun"),
    ],
)
