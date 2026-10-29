
corpus/
├── translations/                    # Raw MT outputs by source
│   ├── google_sheets_import_2026-10-29.csv
│   └── raw_translations.tsv
├── validated/                       # Post-quality filtering
│   ├── high_confidence.csv          # Confidence > 0.8
│   ├── medium_confidence.csv        # Confidence 0.6-0.8
│   └── review_needed.csv            # Low confidence or edge cases
├── glossaries/                      # Terminology databases
│   ├── core_terms.json              # Essential game vocabulary
│   ├── dlc_terms.json               # DLC-specific terms
│   └── location_names.txt           # Place names & locations
└── formid_index/                    # Lookup tables
    ├── dialogue_group_ids.txt       # FormIDs in Dialogue groups
    └── miscellaneous.csv            # Other record types
```

---

## 🎯 Step 4: Priority Assignment Strategy

### Translation Priority Scale

| Priority | Components | Target Completion | MT Provider Quality |
|----------|-----------|-------------------|---------------------|
| P0 - Critical | Core game (`FalloutNV.esm`) | Phase 1 complete | High-priority only |
| P1 - Essential | 5 DLCs (DM, HH, OWB, LR, GRA) | Phase 2 complete | Standard MT + review |
| P2 - Important | YUP unofficial patch | Phase 3 (optional) | Selective translation |
| P3 - Nice-to-have | Major mods (JSawyer, Dark Side) | Future phases | As resources allow |

### Priority Filtering Logic

```python
def assign_priority(record):
    record_type = record['RecordType']
    form_id_group = get_formid_group(record['FormID'])
    
    if record_type in ['Dialogue', 'Message', 'Name']:
        priority = 0 if form_id_group == 'core' else 1
    elif record_type in ['Quest', 'ItemDescription']:
        priority = 1
    else:
        priority = 2
    
    return priority
```

---

## ✍️ Step 5: Human Post-Editing Workflow

### Review Guidelines

1. **Contextual Accuracy**: Ensure translations make sense within game dialogue flow
2. **Character Voice**: Match speaker tone (heroic, sarcastic, menacing, etc.)
3. **Cultural Appropriateness**: Avoid inappropriate humor or references for Thai audience
4. **Terminology Consistency**: Use glossary terms where applicable

### Review Tools Setup

Configure translation memory and QA scripts:

```bash
# After xtranslator processing
pip install translate-toolkit memsource-connector quality-assurance-tools

# Run validation
python pipeline/xtranslator/validate_translations.py --input corpus/validated/high_confidence.csv
```

---

## 🚀 Running the Pipeline

### Complete Translation Batch


```
pipeline/
├── xtranslator/                    # Main translation tool
│   ├── config.json                 # Tool configuration
│   ├── templates/                  # Text extraction templates
│   ├── output/                     # Extracted text records
│   └── scripts/                    # Helper scripts for MT
├── importers/                      # Data source connectors
│   └── google_sheets.py            # Google Sheets CSV importer
├── corpus/                         # Aggregated translation database
│   ├── translations.csv            # All translated strings
│   ├── glossary.json               # Terminology standards
│   └── formid_index.txt            # FormID lookup table
└── priority/                       # Translation priority lists
    ├── core_game.csv               # FalloutNV.esm (highest)
    ├── dlc1_dead_money.csv         # DLC: Dead Money
    ├── dlc2_honest_hearts.csv      # DLC: Honest Hearts
    ├── dlc3_old_world_blues.csv    # DLC: Old World Blues
    ├── dlc4_lonesome_road.csv      # DLC: Lonesome Road
    ├── dlc5_gunrunners_arsenal.csv # DLC: Gun Runners Arsenal
    ├── yup_unofficial_patch.csv    # YUP patch translations
    └── major_mods.csv              # JSawyer, Dark Side series, etc.
```



### Glossary Standards
corpus/







### File Outputs

After pipeline processing, outputs go to:

```
corpus/
└── final_translations/
    ├── FalloutNV.esm_translations.csv      # Core game translations
    ├── dm_translations.csv                  # Dead Money
    ├── hh_translations.csv                  # Honest Hearts
    ├── owb_translations.csv                 # Old World Blues
    ├── lr_translations.csv                  # Lonesome Road
    └── gra_translations.csv                 # Gun Runners Arsenal
```

These files will be used for:
- ESP/ESM modification tools (FNVEdit, etc.)
- Integration into mod archives
- Version control and distribution

---

## 🛡️ Best Practices

1. **Always backup**: Commit to git after major corpus updates
2. **Track changes**: Use semantic versioning for corpus releases
3. **Document decisions**: Record MT choices, rejection reasons in commit messages
4. **Test frequently**: Verify translations render correctly with font slots
5. **Collaborate**: Maintain shared glossary for consistency across translators

---

## 📚 References

- [xtranslator Documentation](./xtranslator/README.md)
- [Corpus Schema Definition](./corpus/schema.md)
- [Google Sheets Export Guide](https://support.google.com/docs/answer/15294)
- [FNVEdit Editing Guide](http://fallout.newvegas.fandom.com/wiki/Fallout_New_Vegas_Edition#Editing_the_ESP)

---

*Document maintained by ThaiFNV Development Team. For questions, see the project GitHub repository.*
```
### File Outputs

After pipeline processing, outputs go to:

```
corpus/
└── final_translations/
    ├── FalloutNV.esm_translations.csv      # Core game translations
    ├── dm_translations.csv                  # Dead Money
    ├── hh_translations.csv                  # Honest Hearts
    ├── owb_translations.csv                 # Old World Blues
    ├── lr_translations.csv                  # Lonesome Road
    └── gra_translations.csv                 # Gun Runners Arsenal
```

These files will be used for:
- ESP/ESM modification tools (FNVEdit, etc.)
- Integration into mod archives
- Version control and distribution

---

## 🛡️ Best Practices

### Generate Progress Report

```bash
python pipeline/reports/generate_progress.py \
    --metrics-file metrics/pipeline_metrics.csv \
    --output reports/translation_status_2026-10-29.md
```

### Metrics Tracked

- **Total strings processed**: Count of unique records from source
- **MT confidence distribution**: Histogram of confidence scores
- **High-confidence translations**: Strings passing quality threshold
- **Review backlog**: Items requiring human post-editing
- **Priority completion**: Percentage by P0/P1/P2 levels

---

## 🔗 Integration with Main Project

```bash
cd D:/backup/github/ThaiFNV/pipeline/xtranslator

# Step 1: Import Google Sheet data
python importers/google_sheets_importer.py \
    --source "corpus/imported" \
    --output "corpus/translations" \
    --format csv

# Step 2: Run xtranslator for MT processing
python xtranslator/main.py \
    --input corpus/imported/*.csv \
    --mt-model google_translate_thai \
    --output corpus/validated/processed.tsv \
    --threshold 0.7

# Step 3: Filter by priority
python scripts/prioritize_translations.py \
    --input corpus/validated/processed.tsv \
    --output-dir corpus/priority/P0_core_game \
    --priority-levels core=high dlc=medium patch=low

# Step 4: Generate glossary updates
python scripts/update_glossary.py \
    --corpus corpus/priority/P0_core_game/*.csv \
    --glossary-output corpus/glossaries/core_terms.json

# Step 5: Export for human review
python scripts/export_review_bundle.py \
    --input corpus/validated/processed.tsv \
    --output "corpus/exports/final_review_bundle.zip"
```

---

## 📈 Monitoring & Reporting

Configure translation memory and QA scripts:

```bash
# After xtranslator processing
pip install translate-toolkit memsource-connector quality-assurance-tools

# Run validation
python pipeline/xtranslator/validate_translations.py --input corpus/validated/high_confidence.csv
```

---

## 🚀 Running the Pipeline

### Complete Translation Batch

### Review Guidelines

1. **Contextual Accuracy**: Ensure translations make sense within game dialogue flow
2. **Character Voice**: Match speaker tone (heroic, sarcastic, menacing, etc.)
3. **Cultural Appropriateness**: Avoid inappropriate humor or references for Thai audience
4. **Terminology Consistency**: Use glossary terms where applicable

### Review Tools Setup

Configure translation memory and QA scripts:

```bash
# After xtranslator processing
pip install translate-toolkit memsource-connector quality-assurance-tools

# Run validation
python pipeline/xtranslator/validate_translations.py --input corpus/validated/high_confidence.csv
```

---

## 🚀 Running the Pipeline

### Translation Priority Scale

| Priority | Components | Target Completion | MT Provider Quality |
|----------|-----------|-------------------|---------------------|
| P0 - Critical | Core game (`FalloutNV.esm`) | Phase 1 complete | High-priority only |
| P1 - Essential | 5 DLCs (DM, HH, OWB, LR, GRA) | Phase 2 complete | Standard MT + review |
| P2 - Important | YUP unofficial patch | Phase 3 (optional) | Selective translation |
| P3 - Nice-to-have | Major mods (JSawyer, Dark Side) | Future phases | As resources allow |

### Priority Filtering Logic

```python
def assign_priority(record):
    record_type = record['RecordType']
    form_id_group = get_formid_group(record['FormID'])
    
    if record_type in ['Dialogue', 'Message', 'Name']:
        priority = 0 if form_id_group == 'core' else 1
    elif record_type in ['Quest', 'ItemDescription']:
        priority = 1
    else:
        priority = 2
    
    return priority
```

---

## ✍️ Step 5: Human Post-Editing Workflow

├── translations/                    # Raw MT outputs by source
│   ├── google_sheets_import_2026-10-29.csv
│   └── raw_translations.tsv
├── validated/                       # Post-quality filtering
│   ├── high_confidence.csv          # Confidence > 0.8
│   ├── medium_confidence.csv        # Confidence 0.6-0.8
│   └── review_needed.csv            # Low confidence or edge cases
├── glossaries/                      # Terminology databases
│   ├── core_terms.json              # Essential game vocabulary
│   ├── dlc_terms.json               # DLC-specific terms
│   └── location_names.txt           # Place names & locations
└── formid_index/                    # Lookup tables
    ├── dialogue_group_ids.txt       # FormIDs in Dialogue groups
    └── miscellaneous.csv            # Other record types
```

---

## 🎯 Step 4: Priority Assignment Strategy


Establish consistent terminology for key concepts:

| English Term | Thai Translation | Notes |
|-------------|-----------------|-------|
| Fallout | ฟอลแลท | Game title, standard transliteration |
| New Vegas | นูวegas | Proper noun handling |
| Brotherhood of Steel | บราเธอฮุดออฟสตีล | Established mod terminology |
| Pip-Boy | พิปบอย | Device name |
| Vault | วัลต์ | Shelter system |
| Guts and Glory | กัตส์แอนด์กลอรี่ | Book reference |

### File Organization in `corpus/`

```
### xtranslator config.json Template

```json
{
  "project": "ThaiFNV",
  "workspaces": {
    "source": "D:/backup/github/ThaiFNV",
    "corpus": "D:/backup/github/ThaiFNV/corpus",
    "pipeline": "D:/backup/github/ThaiFNV/pipeline"
  },
  "mt_providers": {
    "default": "google_translator_api",
    "fallback": "deep_l",
    "api_key_env": "GTM_API_KEY"
  },
  "quality_thresholds": {
    "confidence_min": 0.7,
    "length_variance_max": 0.2
  },
  "output_formats": {
    "csv": true,
    "tsv": false,
    "jsonl": true
  }
}
```

---

## 📊 Step 3: Corpus Management

## 🔄 Pipeline Workflow

```bash
pipeline/
├── xtranslator/                    # Main translation tool
│   ├── config.json                 # Tool configuration
│   ├── templates/                  # Text extraction templates
│   ├── output/                     # Extracted text records
│   └── scripts/                    # Helper scripts for MT
├── importers/                      # Data source connectors
│   └── google_sheets.py            # Google Sheets CSV importer
├── corpus/                         # Aggregated translation database
│   ├── translations.csv            # All translated strings
│   ├── glossary.json               # Terminology standards
│   └── formid_index.txt            # FormID lookup table
└── priority/                       # Translation priority lists
    ├── core_game.csv               # FalloutNV.esm (highest)
    ├── dlc1_dead_money.csv         # DLC: Dead Money
    ├── dlc2_honest_hearts.csv      # DLC: Honest Hearts
    ├── dlc3_old_world_blues.csv    # DLC: Old World Blues
    ├── dlc4_lonesome_road.csv      # DLC: Lonesome Road
    ├── dlc5_gunrunners_arsenal.csv # DLC: Gun Runners Arsenal
    ├── yup_unofficial_patch.csv    # YUP patch translations
    └── major_mods.csv              # JSawyer, Dark Side series, etc.
```


---

## 📋 Overview

This guide outlines the workflow for processing Thai translations through the xtranslator pipeline, integrating data from Google Sheets and managing translation assets.

---

### xtranslator config.json Template

```json
{
  "project": "ThaiFNV",
  "workspaces": {
    "source": "D:/backup/github/ThaiFNV",
    "corpus": "D:/backup/github/ThaiFNV/corpus",
    "pipeline": "D:/backup/github/ThaiFNV/pipeline"
  },
  "mt_providers": {
    "default": "google_translator_api",
    "fallback": "deep_l",
    "api_key_env": "GTM_API_KEY"
  },
  "quality_thresholds": {
    "confidence_min": 0.7,
    "length_variance_max": 0.2
  },
  "output_formats": {
    "csv": true,
    "tsv": false,
    "jsonl": true
  }
}
```

---

## 📊 Step 3: Corpus Management

### Glossary Standards

Establish consistent terminology for key concepts:

| English Term | Thai Translation | Notes |
|-------------|-----------------|-------|
| Fallout | ฟอลแลท | Game title, standard transliteration |
| New Vegas | นูวegas | Proper noun handling |
| Brotherhood of Steel | บราเธอฮุดออฟสตีล | Established mod terminology |
| Pip-Boy | พิปบอย | Device name |
| Vault | วัลต์ | Shelter system |
| Guts and Glory | กัตส์แอนด์กลอรี่ | Book reference |

### File Organization in `corpus/`

```


## 📋 Overview

This guide outlines the workflow for processing Thai translations through the xtranslator pipeline, integrating data from Google Sheets and managing translation assets.

---

## 🔄 Pipeline Workflow

```bash


┌─────────────────────────────────────────────────────────────┐
│                    Translation Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Source Data Import                                         │
│     └── Google Sheets → CSV Export                            │
│                                                                 │
│ 2. xtranslator Processing                                      │
│     ├── Text Extraction from ESP/ESM files                    │
│     ├── Machine Translation (MT) Seed Generation              │
│     └── Quality Filtering & Deduplication                      │
│                                                                 │
│ 3. Corpus Integration                                          │
│     └── Merge with existing corpus (`corpus/`)                │
│                                                                 │
│ 4. Priority Assignment                                         │
│     └── Categorize by game component (core/DLCs/patches)     │
│                                                                 │
│ 5. Human Post-Editing Workflow                                 │
│     └── Translation Memory & Glossary Management               │
└─────────────────────────────────────────────────────────────┘

---

## 📥 Step 1: Import Google Sheet Translations

### Source Data Location

- **Google Sheet URL**: [Thai Translation Spreadsheet](https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE/edit?usp=sharing)
- **Expected Columns**: `FormID`, `EditorID`, `OriginalText` (English), `ThaiTranslation`, `RecordType`

### Import Process

1. Export Google Sheet as CSV
2. Validate column headers match expected schema
3. Run through xtranslator for integration processing

---

## 🔧 Step 2: xtranslator Configuration

### Directory Structure

```

## 📋 Overview
# Pipeline Guide - ThaiFNV Translation Processing

## 📋 Overview

This guide outlines the workflow for processing Thai translations through the xtranslator pipeline, integrating data from Google Sheets and managing translation assets.

---

## 🔄 Pipeline Workflow

```bash

┌─────────────────────────────────────────────────────────────┐
│                    Translation Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Source Data Import                                         │
│     └── Google Sheets → CSV Export                            │
│                                                                 │
│ 2. xtranslator Processing                                      │
│     ├── Text Extraction from ESP/ESM files                    │
│     ├── Machine Translation (MT) Seed Generation              │
│     └── Quality Filtering & Deduplication                      │
│                                                                 │
│ 3. Corpus Integration                                          │
│     └── Merge with existing corpus (`corpus/`)                │
│                                                                 │
│ 4. Priority Assignment                                         │
│     └── Categorize by game component (core/DLCs/patches)     │
│                                                                 │
│ 5. Human Post-Editing Workflow                                 │
│     └── Translation Memory & Glossary Management               │
└─────────────────────────────────────────────────────────────┘

---

## 📥 Step 1: Import Google Sheet Translations

### Source Data Location

- **Google Sheet URL**: [Thai Translation Spreadsheet](https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE/edit?usp=sharing)
- **Expected Columns**: `FormID`, `EditorID`, `OriginalText` (English), `ThaiTranslation`, `RecordType`

### Import Process

1. Export Google Sheet as CSV
2. Validate column headers match expected schema
3. Run through xtranslator for integration processing

---

## 🔧 Step 2: xtranslator Configuration

# Pipeline Guide - ThaiFNV Translation Processing
corpus/
├── translations/                    # Raw MT outputs by source
│   ├── google_sheets_import_2026-10-29.csv
│   └── raw_translations.tsv
├── validated/                       # Post-quality filtering
│   ├── high_confidence.csv          # Confidence > 0.8
│   ├── medium_confidence.csv        # Confidence 0.6-0.8
│   └── review_needed.csv            # Low confidence or edge cases
├── glossaries/                      # Terminology databases
│   ├── core_terms.json              # Essential game vocabulary
│   ├── dlc_terms.json               # DLC-specific terms
│   └── location_names.txt           # Place names & locations
└── formid_index/                    # Lookup tables
    ├── dialogue_group_ids.txt       # FormIDs in Dialogue groups
    └── miscellaneous.csv            # Other record types
```

---

## 🎯 Step 4: Priority Assignment Strategy

### Translation Priority Scale

| Priority | Components | Target Completion | MT Provider Quality |
|----------|-----------|-------------------|---------------------|
| P0 - Critical | Core game (`FalloutNV.esm`) | Phase 1 complete | High-priority only |
| P1 - Essential | 5 DLCs (DM, HH, OWB, LR, GRA) | Phase 2 complete | Standard MT + review |
| P2 - Important | YUP unofficial patch | Phase 3 (optional) | Selective translation |
| P3 - Nice-to-have | Major mods (JSawyer, Dark Side) | Future phases | As resources allow |

### Priority Filtering Logic

```python
def assign_priority(record):
    record_type = record['RecordType']
    form_id_group = get_formid_group(record['FormID'])
    
    if record_type in ['Dialogue', 'Message', 'Name']:
        priority = 0 if form_id_group == 'core' else 1
    elif record_type in ['Quest', 'ItemDescription']:
        priority = 1
    else:
        priority = 2
    
    return priority
```

---

## ✍️ Step 5: Human Post-Editing Workflow

### Review Guidelines

1. **Contextual Accuracy**: Ensure translations make sense within game dialogue flow
2. **Character Voice**: Match speaker tone (heroic, sarcastic, menacing, etc.)
3. **Cultural Appropriateness**: Avoid inappropriate humor or references for Thai audience
4. **Terminology Consistency**: Use glossary terms where applicable

### Review Tools Setup

Configure translation memory and QA scripts:

```bash
# After xtranslator processing
pip install translate-toolkit memsource-connector quality-assurance-tools

# Run validation
python pipeline/xtranslator/validate_translations.py --input corpus/validated/high_confidence.csv
```

---

## 🚀 Running the Pipeline

### Complete Translation Batch

```bash
cd D:/backup/github/ThaiFNV/pipeline/xtranslator

# Step 1: Import Google Sheet data
python importers/google_sheets_importer.py \
    --source "corpus/imported" \
    --output "corpus/translations" \
    --format csv

# Step 2: Run xtranslator for MT processing
python xtranslator/main.py \
    --input corpus/imported/*.csv \
    --mt-model google_translate_thai \
    --output corpus/validated/processed.tsv \
    --threshold 0.7

# Step 3: Filter by priority
python scripts/prioritize_translations.py \
    --input corpus/validated/processed.tsv \
    --output-dir corpus/priority/P0_core_game \
    --priority-levels core=high dlc=medium patch=low

# Step 4: Generate glossary updates
python scripts/update_glossary.py \
    --corpus corpus/priority/P0_core_game/*.csv \
    --glossary-output corpus/glossaries/core_terms.json

# Step 5: Export for human review
python scripts/export_review_bundle.py \
    --input corpus/validated/processed.tsv \
    --output "corpus/exports/final_review_bundle.zip"
```

---

## 📈 Monitoring & Reporting

### Generate Progress Report

```bash
python pipeline/reports/generate_progress.py \
    --metrics-file metrics/pipeline_metrics.csv \
    --output reports/translation_status_2026-10-29.md
```

### Metrics Tracked

- **Total strings processed**: Count of unique records from source
- **MT confidence distribution**: Histogram of confidence scores
- **High-confidence translations**: Strings passing quality threshold
- **Review backlog**: Items requiring human post-editing
- **Priority completion**: Percentage by P0/P1/P2 levels

---

## 🔗 Integration with Main Project

### File Outputs

After pipeline processing, outputs go to:

```
corpus/
└── final_translations/
    ├── FalloutNV.esm_translations.csv      # Core game translations
    ├── dm_translations.csv                  # Dead Money
    ├── hh_translations.csv                  # Honest Hearts
    ├── owb_translations.csv                 # Old World Blues
    ├── lr_translations.csv                  # Lonesome Road
    └── gra_translations.csv                 # Gun Runners Arsenal
```

These files will be used for:
- ESP/ESM modification tools (FNVEdit, etc.)
- Integration into mod archives
- Version control and distribution

---

## 🛡️ Best Practices

1. **Always backup**: Commit to git after major corpus updates
2. **Track changes**: Use semantic versioning for corpus releases
3. **Document decisions**: Record MT choices, rejection reasons in commit messages
4. **Test frequently**: Verify translations render correctly with font slots
5. **Collaborate**: Maintain shared glossary for consistency across translators

---

## 📚 References

- [xtranslator Documentation](./xtranslator/README.md)
- [Corpus Schema Definition](./corpus/schema.md)
- [Google Sheets Export Guide](https://support.google.com/docs/answer/15294)
- [FNVEdit Editing Guide](http://fallout.newvegas.fandom.com/wiki/Fallout_New_Vegas_Edition#Editing_the_ESP)

---

*Document maintained by ThaiFNV Development Team. For questions, see the project GitHub repository.*
## 📊 Step 3: Corpus Management

### Glossary Standards

Establish consistent terminology for key concepts:

| English Term | Thai Translation | Notes |
|-------------|-----------------|-------|
| Fallout | ฟอลแลท | Game title, standard transliteration |
| New Vegas | นูวegas | Proper noun handling |
| Brotherhood of Steel | บราเธอฮุดออฟสตีล | Established mod terminology |
| Pip-Boy | พิปบอย | Device name |
| Vault | วัลต์ | Shelter system |
| Guts and Glory | กัตส์แอนด์กลอรี่ | Book reference |

### File Organization in `corpus/`

```
┌─────────────────────────────────────────────────────────────┐
│                    Translation Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Source Data Import                                         │
│     └── Google Sheets → CSV Export                            │
│                                                                 │
│ 2. xtranslator Processing                                      │
│     ├── Text Extraction from ESP/ESM files                    │
│     ├── Machine Translation (MT) Seed Generation              │
│     └── Quality Filtering & Deduplication                      │
│                                                                 │
│ 3. Corpus Integration                                          │
│     └── Merge with existing corpus (`corpus/`)                │
│                                                                 │
│ 4. Priority Assignment                                         │
│     └── Categorize by game component (core/DLCs/patches)     │
│                                                                 │
│ 5. Human Post-Editing Workflow                                 │
│     └── Translation Memory & Glossary Management               │
└─────────────────────────────────────────────────────────────┘

---

## 📥 Step 1: Import Google Sheet Translations

### Source Data Location

- **Google Sheet URL**: [Thai Translation Spreadsheet](https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE/edit?usp=sharing)
- **Expected Columns**: `FormID`, `EditorID`, `OriginalText` (English), `ThaiTranslation`, `RecordType`

### Import Process

1. Export Google Sheet as CSV
2. Validate column headers match expected schema
3. Run through xtranslator for integration processing

---

## 🔧 Step 2: xtranslator Configuration

### Directory Structure

```
pipeline/
├── xtranslator/                    # Main translation tool
│   ├── config.json                 # Tool configuration
│   ├── templates/                  # Text extraction templates
│   ├── output/                     # Extracted text records
│   └── scripts/                    # Helper scripts for MT
├── importers/                      # Data source connectors
│   └── google_sheets.py            # Google Sheets CSV importer
├── corpus/                         # Aggregated translation database
│   ├── translations.csv            # All translated strings
│   ├── glossary.json               # Terminology standards
│   └── formid_index.txt            # FormID lookup table
└── priority/                       # Translation priority lists
    ├── core_game.csv               # FalloutNV.esm (highest)
    ├── dlc1_dead_money.csv         # DLC: Dead Money
    ├── dlc2_honest_hearts.csv      # DLC: Honest Hearts
    ├── dlc3_old_world_blues.csv    # DLC: Old World Blues
    ├── dlc4_lonesome_road.csv      # DLC: Lonesome Road
    ├── dlc5_gunrunners_arsenal.csv # DLC: Gun Runners Arsenal
    ├── yup_unofficial_patch.csv    # YUP patch translations
    └── major_mods.csv              # JSawyer, Dark Side series, etc.
```

### xtranslator config.json Template

```json
{
  "project": "ThaiFNV",
  "workspaces": {
    "source": "D:/backup/github/ThaiFNV",
    "corpus": "D:/backup/github/ThaiFNV/corpus",
    "pipeline": "D:/backup/github/ThaiFNV/pipeline"
  },
  "mt_providers": {
    "default": "google_translator_api",
    "fallback": "deep_l",
    "api_key_env": "GTM_API_KEY"
  },
  "quality_thresholds": {
    "confidence_min": 0.7,
    "length_variance_max": 0.2
  },
  "output_formats": {
    "csv": true,
    "tsv": false,
    "jsonl": true
  }
}
```

---


## 📋 Overview

This guide outlines the workflow for processing Thai translations through the xtranslator pipeline, integrating data from Google Sheets and managing translation assets.

---

## 🔄 Pipeline Workflow

```bash
