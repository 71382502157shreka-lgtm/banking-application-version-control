"""
Script to analyze actual repository file counts and line counts by language.
Excludes virtual environments, .git, cache files, build folders, and database files.
"""
import os

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules", "instance",
    ".pytest_cache", ".gemini", "brain", "artifacts", "build", "dist"
}

EXTENSION_MAP = {
    ".py": "Python",
    ".html": "HTML",
    ".css": "CSS",
    ".js": "JavaScript"
}


def analyze_repository(root_dir):
    stats = {
        "Python": {"files": 0, "lines": 0},
        "HTML": {"files": 0, "lines": 0},
        "CSS": {"files": 0, "lines": 0},
        "JavaScript": {"files": 0, "lines": 0}
    }

    for current_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXTENSION_MAP:
                lang = EXTENSION_MAP[ext]
                filepath = os.path.join(current_root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = len(f.readlines())
                    stats[lang]["files"] += 1
                    stats[lang]["lines"] += lines
                except Exception as e:
                    print(f"Warning: Failed to read {filepath}: {e}")

    total_files = sum(s["files"] for s in stats.values())
    total_lines = sum(s["lines"] for s in stats.values())

    print("=" * 60)
    print("BANKVCS 2.0 - REPOSITORY LANGUAGE STATISTICS")
    print("=" * 60)
    for lang, data in stats.items():
        pct_files = (data["files"] / total_files * 100) if total_files else 0
        pct_lines = (data["lines"] / total_lines * 100) if total_lines else 0
        print(f"{lang:<12}: {data['files']:>4} files ({pct_files:>5.1f}%) | {data['lines']:>6} lines ({pct_lines:>5.1f}%)")

    print("-" * 60)
    print(f"Total       : {total_files:>4} files         | {total_lines:>6} lines")
    print("=" * 60)

    return stats, total_files, total_lines


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    analyze_repository(project_root)
