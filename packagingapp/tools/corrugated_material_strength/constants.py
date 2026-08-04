from decimal import Decimal


GRAVITY_M_S2 = Decimal("9.80665")
GENERIC_CO2_FACTOR_KG_PER_KG = Decimal("0.491")
ECT_LB_IN_TO_KN_M = Decimal("0.175126835")

WALL_SINGLE = "SINGLE_WALL"
WALL_DOUBLE = "DOUBLE_WALL"

SOURCE_TYPES = (
    ("OFFICIAL_REFERENCE", "Official reference"),
    ("ILLUSTRATIVE_DERIVED", "Illustrative derived"),
    ("ADMIN_ENTERED", "Admin entered"),
    ("SUPPLIER_DOCUMENTED", "Supplier documented"),
    ("COMPANY_MEASURED", "Company measured"),
)

FLUTE_CHOICES = tuple((code, code) for code in ("A", "B", "C", "E", "F", "N"))
REFERENCE_FLUTE_FAMILY_CHOICES = (
    ("A", "A flute"), ("B", "B flute"), ("C", "C flute"),
    ("E", "E flute"), ("F", "F flute"), ("N", "N flute"),
    ("EB", "EB double wall"), ("BC", "BC double wall"),
)
CALIPER_BASIS_CHOICES = (
    ("GRADE_SPECIFIC_TARGET", "Grade-specific target caliper"),
    ("FLUTE_FAMILY_REFERENCE", "Flute-family reference caliper"),
    ("PUBLISHED_RANGE_MIDPOINT", "Midpoint of published range"),
    ("LINEAR_INTERPOLATION", "Linear interpolation between published grades"),
    ("ADMIN_ENTERED", "Admin-entered reference"),
)

PAPER_TYPES = (
    ("KRAFTLINER", "Kraftliner"),
    ("TESTLINER", "Testliner"),
    ("HIGH_PERFORMANCE_RECYCLED_LINER", "High-performance recycled liner"),
    ("KRAFT_TOP_LINER", "Kraft-top liner"),
    ("WHITE_TOP_TESTLINER", "White-top testliner"),
    ("SEMI_CHEMICAL_FLUTING", "Semi-chemical fluting"),
    ("RECYCLED_FLUTING", "Recycled fluting"),
    ("LIGHTWEIGHT_RECYCLED_MEDIUM", "Lightweight recycled medium"),
    ("DUAL_PURPOSE", "Dual-purpose paper"),
    ("UNSPECIFIED_LINER", "Unspecified liner"),
    ("UNSPECIFIED_MEDIUM", "Unspecified medium"),
)

CO2_SOURCE_TYPES = (
    ("GENERIC_INDUSTRY_SCREENING", "Generic industry screening"),
    ("SUPPLIER_SCREENING", "Supplier screening"),
    ("COMPANY_MEASURED", "Company measured"),
    ("OTHER", "Other"),
)

CO2_FACTOR_BASES = (
    ("FINISHED_CORRUGATED_MASS", "Finished corrugated mass"),
    ("REQUIRED_SHEET_MASS", "Required sheet mass"),
    ("SUPPLIER_DEFINED", "Supplier defined"),
)

DISTRIBUTION_FACTORS = {
    "LIGHT": Decimal("2.0"),
    "NORMAL": Decimal("3.0"),
    "DEMANDING": Decimal("5.0"),
}

DISTRIBUTION_CHOICES = (
    ("LIGHT", "Light"),
    ("NORMAL", "Normal"),
    ("DEMANDING", "Demanding"),
    ("CUSTOM", "Custom"),
)

DEFAULTS = {
    "box_length_mm": Decimal("400"),
    "box_width_mm": Decimal("300"),
    "box_height_mm": Decimal("200"),
    "product_weight_g": Decimal("200"),
    "quantity": 1000,
    "fefco_code": "0201",
    "joint_width_mm": Decimal("40"),
    "sheet_margin_per_edge_mm": Decimal("20"),
    "pallet_length_mm": Decimal("1200"),
    "pallet_width_mm": Decimal("800"),
    "pallet_height_mm": Decimal("144"),
    "pallet_weight_kg": Decimal("0"),
    "max_palletized_height_mm": Decimal("1200"),
    "pattern": "COLUMN_ALIGNED",
    "stacked_pallets": 1,
    "distribution_profile": "NORMAL",
    "distribution_factor": DISTRIBUTION_FACTORS["NORMAL"],
    "co2_mode": "CONSTRUCTION",
    "reference_ect_grade_id": "",
}
