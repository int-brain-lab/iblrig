from pathlib import Path

import ibllib.io.raw_data_loaders as raw

import iblrig.path_helper as ph


# Remove empty folders
def check_delete_empty_folders(path, rglob_pattern="*", dry=True):
    data_path = Path(ph.get_iblrig_data_folder())
    all_dirs = {p for p in data_path.rglob(rglob_pattern) if p.is_dir()}
    empty_dirs = {p for p in all_dirs if not list(p.glob("*"))}
    for d in empty_dirs:
        if dry:
            print("Found empty folder:", d)
        elif not dry:
            print("Deleting empty folder: ", d)
            d.rmdir()
    else:
        if dry:
            print(f"Empty folders: {len(empty_dirs)}")
        elif not dry:
            print(f"Deleted folders: {len(empty_dirs)}")


# Check and delete empty files
def check_delete_empty_files(path, rglob_pattern="*", dry=True):
    path = Path(path)
    excludes = [".log", ".error", ".flatiron", ".flag"]
    all_files = {
        p for p in path.rglob(f"{rglob_pattern}") if p.is_file() and p.suffix not in excludes
    }
    empty_files = 0
    for f in all_files:
        if f.stat().st_size == 0:
            empty_files += 1
            if dry:
                print("Found empty file:", f)
            elif not dry:
                print("Deleting empty file: ", f)
                f.unlink()
            continue
    else:
        if dry:
            print(f"Empty files: {empty_files}")
        elif not dry:
            print(f"Deleted files: {empty_files}")


# Find sessions
def find_sessions(path, rglob_pattern="*taskSettings*"):
    path = Path(path)
    sessions = {p.parent.parent for p in path.rglob(rglob_pattern) if p.is_file()}
    print(f"Found sessions: {len(sessions)}")
    return sessions


def get_names(session_list):
    names = ["/".join(s.parts[-3:]) for s in session_list]
    return names


def get_mice(session_list):
    names = {s.parts[-3] for s in session_list}
    return names


def get_dates(session_list):
    names = {s.parts[-2] for s in session_list}
    return names


# Load
def load_session_settings(path_list):
    path_list = [Path(path) for path in path_list]
    settings = []
    for s in path_list:
        settings.append(raw.load_settings(s))
    return settings


if __name__ == "__main__":
    data_path = Path(ph.get_iblrig_data_folder())
    check_delete_empty_files(data_path, "taskSettings")
    check_delete_empty_folders(data_path)
    sessions_with_settings = find_sessions(data_path, rglob_pattern="*taskSettings*")
    sessions_with_data = find_sessions(data_path, rglob_pattern="*taskData*")
    settings = load_session_settings(sessions_with_settings)
