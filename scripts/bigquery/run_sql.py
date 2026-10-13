"""Run a SQL template against an explicitly selected deployment environment."""

import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.deployment import ENVIRONMENTS, load_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=ENVIRONMENTS)
    parser.add_argument("file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_environment(args.environment)
    sql = args.file.read_text().replace("YOUR_PROJECT_ID", config["project_id"])
    command = ["bq", f'--project_id={config["project_id"]}',
               f'--location={config["region"]}', "query", "--use_legacy_sql=false"]
    if args.dry_run:
        command.append("--dry_run")
    subprocess.run(command, input=sql, text=True, check=True)


if __name__ == "__main__":
    main()
