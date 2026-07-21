# CMS Hospital Data Pipeline

A cross-platform Python pipeline for the CMS Provider Data assessment.

## What it does

1. Reads the CMS Provider Data metastore.
2. Selects every CSV distribution whose `theme` contains the exact value `Hospitals`.
3. Compares the dataset's CMS `modified` value and download URL with local SQLite state.
4. Downloads only new or changed distributions.
5. Downloads and processes files concurrently with `ThreadPoolExecutor`.
6. Streams each CSV instead of loading the full dataset into memory.
7. Converts headers to unique `snake_case` names.
8. Atomically publishes completed output files.
9. Tracks dataset state and run-level metrics in SQLite.
10. Writes console and file logs.

CMS metastore endpoint used by this project:

`https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items`

## Project layout

```text
cms_hospital_pipeline/
├── cms_pipeline/
│   ├── catalog.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── models.py
│   ├── naming.py
│   ├── pipeline.py
│   ├── processor.py
│   └── state.py
├── data/
│   ├── processed/
│   └── state/
├── logs/
├── tests/
├── main.py
├── requirements.txt
└── README.md
```

## Setup

Python 3.10 or newer is recommended.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py main.py
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Useful commands

Preview what would run without downloading files:

```bash
python main.py --dry-run
```

Process only two changed files for a quick end-to-end test:

```bash
python main.py --limit 2
```

Force a full refresh:

```bash
python main.py --force
```

Change parallelism:

```bash
python main.py --workers 6
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Incremental-load behavior

The SQLite database is created at:

```text
data/state/cms_pipeline.db
```

A distribution is skipped when all of these remain unchanged:

- The prior status is `SUCCESS`.
- CMS `modified` equals the previously processed value.
- The CMS download URL is unchanged.
- The local output file still exists.

This design also catches a replaced CMS file when its URL changes even if the
catalog's modified date does not.

## Output naming

Files are named with the stable CMS dataset identifier and distribution index,
for example:

```text
ynj2-r877__0__Complications_and_Deaths-Hospital.csv
```

This prevents collisions when different datasets publish files with identical
source filenames.

## Header transformation

Example:

```text
Patients’ rating of the facility linear mean score
```

becomes:

```text
patients_rating_of_the_facility_linear_mean_score
```

Duplicate normalized headers are suffixed:

```text
provider_id, provider_id_2, provider_id_3
```

## Daily scheduling

### Windows Task Scheduler

Create a Basic Task, choose **Daily**, and set:

- Program/script: full path to `.venv\Scripts\python.exe`
- Add arguments: `main.py`
- Start in: full path to this project directory

### Linux cron

Run `crontab -e` and add, for example:

```cron
0 2 * * * cd /opt/cms_hospital_pipeline && /opt/cms_hospital_pipeline/.venv/bin/python main.py >> logs/cron.log 2>&1
```

## Reliability decisions

- HTTP timeouts prevent indefinite hangs.
- Exponential retries handle transient failures.
- Temporary files prevent incomplete CSVs from appearing as successful output.
- SQLite WAL mode supports safe state updates.
- Failed datasets are recorded and retried on the next run.
- SHA-256, row counts, and file sizes provide audit information.

## Assumptions

- CMS's dataset-level `modified` field is the incremental watermark supplied by
  the metastore.
- Only CSV distributions are in scope.
- All CSV data rows are preserved; only the header row is changed.
- A full schema/data-quality framework is outside this assessment's scope.
