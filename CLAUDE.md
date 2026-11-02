# CLAUDE.md — iblrig

## Project Overview

**iblrig** is the International Brain Laboratory's behavioral rig software for neuroscience research. It implements standardized decision-making tasks (ChoiceWorld variants) for training and testing mice. The system controls:
- **Bpod** finite state machine (SanWorks) for behavioral task logic and hardware
- **Bonsai** (Windows only) for visual stimuli
- A **Qt GUI** ("wizard") for task setup, monitoring, and hardware validation

---

## Tech Stack

- **Python:** 3.10 exactly (`==3.10.*`)
- **Build system:** PDM backend (`pdm-backend`)
- **Package manager:** UV
- **Linter/Formatter:** Ruff
- **Testing:** pytest, pytest-cov, pytest-qt, pytest-xvfb
- **Validation:** Pydantic v2
- **GUI:** PyQt5 / qtpy / PyQtGraph
- **Key IBL libs:** ibllib, iblutil, iblpybpod-no-gui, ONE-api, iblqt

---

## Development Setup

```bash
# Install with test + doc dependencies
uv sync --no-default-groups --group test --group doc

# Or with CI extras
uv sync --no-default-groups --group test --group ci --extra project-extraction
```

Settings files (not committed):
1. Copy `settings/hardware_settings_template.yaml` → `settings/hardware_settings.yaml`
2. Copy `settings/iblrig_settings_template.yaml` → `settings/iblrig_settings.yaml`
3. Edit with rig-specific values (COM ports, calibration, folder paths)

See `settings/README.md` for details.

---

## Running Tests

```bash
# Run all tests (with coverage)
pytest
```

Test config in `pyproject.toml`:
- Test paths: `iblrig/test/`
- Coverage: `iblrig` and `iblrig_tasks` packages
- Qt tests use xvfb on CI (`QT_QPA_PLATFORM=offscreen`)

---

## Linting & Formatting

**Tool:** Ruff (configured in `pyproject.toml` under `[tool.ruff]`)

```bash
# Check
ruff check .

# Format
ruff format .

# Fix auto-fixable issues
ruff check --fix .
```

Key settings:
- Line length: **130**
- Quote style: **single quotes**
- Docstring convention: **NumPy**
- Target: Python 3.10

Generated GUI files (`ui_*.py`, `*_rc.py`) are excluded from linting.

---

## Project Structure

```

iblrig/                          # Main Python package
├── base_tasks.py                # BaseSession class, hardware mixins, session lifecycle
├── base_choice_world.py         # ChoiceWorld task logic (~2000 lines), state machine
├── choiceworld.py               # Training history, adaptive reward, contrast logic
├── hardware.py                  # Bpod singleton (thread-safe), RotaryEncoder, audio
├── hardware_validation.py       # Hardware validation routines
├── path_helper.py               # Settings loading (YAML), path management
├── pydantic_definitions.py      # HardwareSettings, RigSettings Pydantic v2 models
├── video.py                     # Video capture (Spinnaker/FLIR), frame extraction
├── ephys.py                     # Ephys session utilities
├── neurophotometrics.py         # Photometry hardware integration
├── net.py                       # Async UDP/TCP network comms between distributed rigs
├── transfer_experiments.py      # Data transfer with BLAKE2B checksum verification
├── sound.py                     # Audio synthesis (sine, noise, Hanning envelopes)
├── gui/                         # PyQt5 GUI
│   ├── wizard.py                # Main task wizard (task selection, subject, hardware)
│   ├── online_plots.py          # Real-time session monitoring (plots → PNG → Alyx)
│   └── validation.py            # Hardware validation GUI
├── test/                        # Test suite
│   └── tasks/                   # Task-specific tests
└── commands.py / tools.py       # CLI commands and utilities

iblrig_tasks/                    # Task implementations (one dir per task variant)
├── _iblrig_tasks_trainingChoiceWorld/task.py
├── _iblrig_tasks_biasedChoiceWorld/task.py
├── _iblrig_tasks_advancedChoiceWorld/task.py
├── _iblrig_tasks_ephysChoiceWorld/task.py
├── _iblrig_tasks_passiveChoiceWorld/task.py
└── ...

settings/                        # Config templates (actual settings are git-ignored)
Bonsai/                          # Bonsai visual stim executable (Windows)
docs/                            # Sphinx documentation
```

---

## Architecture & Key Patterns

### Task Hierarchy
All tasks inherit from `BaseSession` (or specialized subclasses like `TrainingChoiceWorldSession`).
Each task lives in `iblrig_tasks/_iblrig_tasks_<Name>/task.py` and defines a `Session` class.
Task parameters are in `task_parameters.yaml` alongside `task.py`.

### Singleton Hardware
`Bpod` uses a thread-safe singleton — prevents multiple serial connections to the same device.

### State Machine
Bpod sessions define states, transitions, and softcodes (Python callbacks) that implement the behavioral trial logic.

### Data Model
`TrialDataModel` (Pydantic v2) validates behavioral data before saving to binary ALF format.
Session folders use the format `YYYY-MM-DD_NNN/`.

### Settings Hierarchy
1. Hardware settings (COM ports, calibration) — `hardware_settings.yaml`
2. Rig settings (data paths, Alyx credentials) — `iblrig_settings.yaml`
3. Per-task defaults in `task_parameters.yaml`
4. Constants in `iblrig/constants.py`

### Distributed Rigs
`net.py` provides async UDP/TCP communication between rig components (e.g., ephys + behavior PCs) using the `ExpMessage` protocol.

---

## CLI Entry Points

| Command | Purpose |
|---|---|
| `iblrig` | Launch main task wizard GUI |
| `transfer_data` | Transfer behavior data to remote server |
| `transfer_video_data` | Transfer video files |
| `transfer_ephys_data` | Transfer ephys data |
| `flush` | Flush reward valve |
| `validate_iblrig` | Run hardware validation suite |
| `validate_video` | Validate video capture |
| `view_session` | View online monitoring plots |
| `upgrade_iblrig` | Upgrade installation |
| `neuropixel_coordinates` | Register Neuropixel electrode coordinates |

---

## CI/CD

Defined in `.github/workflows/main.yaml`:

1. **Ruff check** (Linux only) — fails fast on style/format issues
2. **Tests** (matrix: Ubuntu + Windows, Python 3.10)
   - Ubuntu installs system audio/display libs
   - Qt tests run with `xvfb-run` / `offscreen` platform
   - Coverage published to Coveralls (parallel)
3. **Coveralls finish** — merges parallel coverage reports

Release workflow (`.github/workflows/release.yaml`): triggered on semver tags, builds Sphinx PDF, creates GitHub release.

---

## Important Notes

- **numpy must be `<2.0.0`** — pinned in pyproject.toml
- **Windows only:** Bonsai visual stimuli; Spinnaker/PySpin video capture
- **Linux only:** xvfb for headless Qt tests in CI
- GUI generated files (`iblrig/gui/ui_*.py`, `*_rc.py`) are auto-generated from `.ui` files — do not edit manually; regenerate with `convert_uis`
- Tasks can be registered as external plugins via Python entry points (since v8.27.0)
