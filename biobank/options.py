"""Schema definitions and controlled-vocabulary option lists.

The categorical option lists were extracted from the lab's data-entry
workbook so the same ready-made choices are offered in the application.
"""

from __future__ import annotations

# Full ordered list of sample fields (matches the lab data form + storage adds).
SAMPLE_FIELDS = [
    "lab_number",
    "sample_number",
    "storage_date",
    "storage_method",
    "freezer_no",
    "shelf_no",
    "plate_no",
    "area",
    "animal_type",
    "sample_type",
    "quantity_ml",
    "concentration",
    "disease",
    "strain",
    "department",
    "barcode",
]

# Fields that only administrators may set when creating/editing a record.
RESTRICTED_FIELDS = ["barcode", "freezer_no", "shelf_no", "plate_no"]

# Fields that must be present on every record.
REQUIRED_FIELDS = ["area", "animal_type", "sample_type", "department"]

# Human-readable labels (used for spreadsheet export headers).
FIELD_LABELS = {
    "lab_number": "Lab number", "sample_number": "Sample number",
    "storage_date": "Storage date", "storage_method": "Storage method",
    "freezer_no": "Freezer no.", "shelf_no": "Shelf no.", "plate_no": "Plate no.",
    "area": "Area", "animal_type": "Animal type", "sample_type": "Sample type",
    "quantity_ml": "Quantity (ml)", "concentration": "Concentration",
    "disease": "Disease", "strain": "Strain", "department": "Department", "barcode": "Barcode",
}

# Numeric fields (coerced to float, stored as REAL).
NUMERIC_FIELDS = ["quantity_ml"]

# Fixed choices for the storage method.
STORAGE_METHODS = ["-20 °C", "-80 °C", "-190 °C"]

# Ready-made controlled vocabularies (from the uploaded workbook).
OPTIONS: dict[str, list[str]] = {
    "area": [
        "Riyadh", "Jeddah", "Makkah", "Madinah", "Dammam", "At-Ta'if", "Tabuk",
        "Buraydah", "Khamis Mushait", "Abha", "Hail", "Najran", "Jizan", "Al Ahsa",
        "Al Qatif", "Arar", "Sakaka", "Al Baha", "Al Kharj", "Unaizah", "Al Qunfudhah",
        "Hafar Al Batin", "Ad Dawadmi", "Al Majma'ah", "Al Quway'iyah", "Wadi ad-Dawasir",
        "Al Aflaj", "Az Zulfi", "Shaqra", "Hotat Bani Tamim", "Afif", "Dhurma",
        "Al Muzahimiyah", "Rumah", "Thadiq", "Huraymila", "Al Hariq", "Al Ghat",
        "Marat", "Ad Dilam",
    ],
    "animal_type": [
        "Cattle", "Sheep", "Gate", "Horse", "Camel", "Chickens", "Birds", "Falcon",
        "Monkey", "Deer", "Donkeys",
    ],
    "sample_type": ["tissue", "swabs", "blood", "Serum", "Fecal", "Skin Scrapings"],
    "disease": [
        "FMD", "PPR", "BTV", "Brucellosis", "Tuberculosis", "Salmonellosis", "E. coli",
        "Clostridial Diseases", "Contagious Caprine Pleuropneumonia", "LSD", "Sheep Pox",
        "Camel Pox", "ORF", "Avian Influenza", "Newcastle Disease", "Rift Valley Fever",
        "Theileriosis", "Trypanosomiasis", "Coccidiosis", "Internal & External Parasites",
        "African Horse Sickness", "Equine Influenza", "Equine Herpesvirus",
        "Equine Infectious Anemia", "Equine Viral Arteritis", "West Nile Fever",
        "Glanders", "Strangles",
    ],
    "strain": ["SAT1", "SAT2", "O", "ASHA1", "ASHA2", "H5", "H9"],
    "department": ["virology", "Parasitic", "Bacterial"],
    "storage_method": STORAGE_METHODS,
}

# Column-header aliases used when importing spreadsheets.
IMPORT_ALIASES = {
    "no": "_no",
    "lab number": "lab_number", "lab #": "lab_number",
    "sample number": "sample_number", "sample #": "sample_number",
    "sample storage date": "storage_date", "storage date": "storage_date",
    "storage method": "storage_method", "storage temp": "storage_method",
    "storage temperature": "storage_method", "storage": "storage_method",
    "preservation": "storage_method",
    "freezer number": "freezer_no", "freezer no": "freezer_no", "freezer no.": "freezer_no",
    "freezer": "freezer_no", "freezer #": "freezer_no", "fridge number": "freezer_no",
    "shelf number": "shelf_no", "shelf no": "shelf_no", "shelf no.": "shelf_no",
    "shelf": "shelf_no", "shelf #": "shelf_no", "rack": "shelf_no", "rack number": "shelf_no",
    "plate number": "plate_no", "plate no": "plate_no", "plate no.": "plate_no",
    "plate": "plate_no", "plate #": "plate_no", "dish number": "plate_no", "dish": "plate_no",
    "area": "area", "region": "area",
    "animal type": "animal_type", "animal": "animal_type",
    "sample type": "sample_type",
    "sample quantity (ml)": "quantity_ml", "sample quantity": "quantity_ml",
    "quantity (ml)": "quantity_ml", "quantity": "quantity_ml", "qty": "quantity_ml",
    "sample concentration": "concentration", "concentration": "concentration", "conc.": "concentration",
    "name of the disease": "disease", "disease": "disease",
    "strain": "strain",
    "department": "department",
    "barcode number": "barcode", "barcode": "barcode",
}
