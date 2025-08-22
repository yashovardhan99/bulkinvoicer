"""Get release notes from the CHANGELOG.md file."""

import sys
import logging

logger = logging.getLogger(__name__)


def main(*args) -> int:
    """Main function to get release notes."""
    changelog_file_path = "CHANGELOG.md"
    version_no = None

    if len(args) > 1:
        for arg in args[1:]:
            if arg.endswith(".md"):
                changelog_file_path = arg
            elif arg.startswith("v"):
                version_no = arg[1:]
                break

    if not version_no:
        raise ValueError("Version number must be specified in the format 'v<version>'")

    with open(changelog_file_path) as file:
        data = file.read()
        start = (
            data.index(f"## [{version_no}]")
            + len(f"## [{version_no}]")
            + len(" - YYYY-MM-DD")
        )
        end = (
            data.index("## [", start + 1)
            if "## [" in data[start + 1 :]
            else data.index("[", start + 1)
            if "[" in data[start + 1 :]
            else len(data)
        )
        release_notes = data[start:end].strip()

    print(release_notes)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(*sys.argv))
