# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview

This repository implements an LRT-2 Train Density & Reporting System: a Django-based web app that monitors real-time passenger density per train and station, simulates station queues, and stores historical logs for daily and weekly congestion analysis.

Key domain concepts (see `passenger_density/main/models.py` and `passenger_density/main/admin.py`):
- `Station`: ordered list of LRT-2 stations.
- `train`: current train state (train ID, max/current capacity, current station, last updated timestamp, computed `capacity_level`).
- `Historicalrecord`: immutable time-stamped snapshots of train density at stations (used for reports).
- `Account`: simple username/password model (used for admin-style access, not Django auth replacement).

The top-level `README.md` contains the conceptual description of algorithms (queues, merge sort, linear search) and the intended reporting features; refer to it when adding new functionality to keep designs consistent.

## Repository layout

- `passenger_density/` – Django project root.
  - `manage.py` – entry point for all Django management commands.
  - `passenger_density/` – project settings and global URL routing.
    - `settings.py` – core configuration (installed apps, database, timezone, static files). Notable:
      - Uses SQLite (`db.sqlite3` in `passenger_density/`).
      - `INSTALLED_APPS` includes only the custom app `main` plus standard Django contrib apps.
      - `TIME_ZONE = 'Asia/Manila'` and `USE_TZ = True` (all new time-aware features should respect this).
    - `urls.py` – mounts Django admin at `/admin/` and delegates the root path to `main.urls`.
  - `main/` – primary application containing domain models, algorithm implementations, and views.
    - `models.py` – defines `Account`, `Station`, `train`, and `Historicalrecord`.
    - `admin.py` – configures the DOTr-style admin dashboard, list views, filters, and display helpers for human-readable timestamps and days.
    - `data.py` – core algorithms and data structures:
      - Linked-list-backed `Queue` and `TrainNode` for FIFO station queue simulation.
      - Generic `merge_sort` and `merge` helpers (descending sort using a provided `key_func`) intended for daily/weekly density reports.
      - Generic `linear_search` for searching entities via an attribute extractor function.
    - `views.py` – request handling and orchestration of models/algorithms:
      - `home` view renders the main dashboard template (`templates/passenger_density/home.html`), which expects a data table (`table_html`), a base64-encoded graph image (`graphic`), and a timestamp (`time`) in the context.
      - `simulate_queue` builds a `Queue` of trains currently at a station (ordered by `last_updated`), then dequeues them to simulate station throughput.
      - `search_train` demonstrates generic `linear_search` over `Train` instances by train ID and returns a human-readable message about train location.
    - `templates/passenger_density/` – Django templates for the passenger density UI (currently `home.html` is present; additional templates referenced by views may need to be created or wired up).
    - `static/bootstrap/` – vendored Bootstrap CSS/JS plus `custom.css` used by the UI; when adjusting styling, modify these rather than adding new CDN links.
  - `db.sqlite3` – local SQLite database for development.
- `msys22/` – local Python environment and third-party packages (e.g., Django, pandas, Pillow). Treat this as an external environment:
  - Do **not** edit code under `msys22/` when changing application behavior.
  - Only touch it if you intentionally need to upgrade or inspect third-party libraries.

## Common commands

All commands below assume you run them from the repository root and then `cd` into the Django project directory:

```bash
cd passenger_density
```

### Environment setup

This project assumes Python 3 and Django (5.x based on `settings.py`). There is no pinned dependency file in the repo; if you are not using the checked-in `msys22` environment, create a virtual environment and install the necessary packages manually.

Create and activate a virtual environment (recommended):

```bash
python -m venv venv
# PowerShell (Windows)
venv\Scripts\Activate.ps1
# or cmd.exe
venv\Scripts\activate.bat
```

Install core dependencies (if needed and not already available in your environment):

```bash
pip install django pandas numpy matplotlib pillow
```

### Running the development server

From `passenger_density/`:

```bash
python manage.py migrate      # ensure database schema is up to date
python manage.py runserver    # start the Django dev server on http://127.0.0.1:8000/
```

Create a Django admin superuser to access the admin dashboard at `/admin/`:

```bash
python manage.py createsuperuser
```

### Tests

There is a placeholder `main/tests.py`; as you add tests, use Django's test runner.

Run all tests for all apps:

```bash
python manage.py test
```

Run tests for a specific app (e.g., `main`):

```bash
python manage.py test main
```

Run a single test case or test method (replace with your actual test paths):

```bash
python manage.py test main.tests.YourTestCase
python manage.py test main.tests.YourTestCase.test_specific_behavior
```

### Linting and formatting

The repository does not currently define a standard linter/formatter configuration (no `pyproject.toml`/`setup.cfg`/`tox.ini` with tools like `ruff`, `flake8`, or `black` at the project root). If you introduce a specific tool, also add its primary invocation command here so future Warp instances can use it consistently.

## Architectural notes and guidelines for changes

- **Keep algorithms in `data.py`, not in views:**
  - When implementing or modifying queueing, sorting, or searching behavior, prefer to extend the generic helpers in `main/data.py` and have views call them rather than inlining algorithms directly into views.
  - For new reporting features (e.g., additional daily/weekly analytics), reuse `merge_sort` and `linear_search` with appropriate `key_func`/attribute extractors instead of writing ad-hoc sorts or searches.

- **Use `Historicalrecord` for analytics, `train` for current state:**
  - `train` represents the current snapshot of a train at a station; it computes a `capacity_level` property from `current_capacity` / `max_capacity`.
  - `Historicalrecord` stores time-series data (train, station, timestamp, passenger count, capacity level). New analytics views should query `Historicalrecord` and operate over collections of these records.

- **Admin as the primary back-office interface:**
  - The Django admin (`/admin/`) is already configured with list displays, search, and filters for `Account`, `Station`, `train`, and `Historicalrecord`.
  - When adding fields to models, update the corresponding `ModelAdmin` classes so administrators can see and filter on the most relevant attributes.

- **Templates and static assets:**
  - The main user-facing page is `main/templates/passenger_density/home.html`, which expects table and graph context variables. When you adjust what the view returns, keep this contract in sync.
  - Front-end layout and theming rely on the vendored Bootstrap assets under `main/static/bootstrap/`. Prefer editing `custom.css` or existing Bootstrap-based structure rather than introducing unrelated frameworks.

- **Timezone and localization:**
  - The project is configured for `Asia/Manila` and uses `django.utils.timezone` for timestamps. When adding new models or views that work with time, use timezone-aware datetimes (`timezone.now()`) and respect this configuration so reports remain consistent.

- **Third-party code under `msys22/`:**
  - Treat the `msys22` directory as an opaque Python environment snapshot. When changing behavior in this project, you should almost always modify files under `passenger_density/main/` or project settings/URLs, not the copies of Django/pandas/etc. living under `msys22/Lib/site-packages/`.
