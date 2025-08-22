"""Update the changelog for a new release.

This script drafts a new release in the CHANGELOG.md file by adding a new section
for the specified version and updating the links accordingly.

This script expects the changelog format to be based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
"""

import sys
import logging
from datetime import date

logger = logging.getLogger(__name__)


def main(*args) -> int:
    """Main function to update the changelog."""
    version_no = None
    changelog_file_path = "CHANGELOG.md"
    unreleased_section = "## [Unreleased]"
    unreleased_url = (
        "https://github.com/yashovardhan99/bulkinvoicer/compare/v{version}...HEAD"
    )
    unreleased_url_label = "[unreleased]: "

    if len(args) > 1:
        for arg in args[1:]:
            if arg.endswith(".md"):
                file = arg
            elif arg.startswith("v"):
                version_no = arg[1:]
                break
    logger.info("Updating changelog for version number:", version_no)

    if not version_no:
        raise ValueError("Version number must be specified in the format 'v<version>'")

    with open(changelog_file_path, mode="r+") as file:
        # Add new section for the version
        data = file.read()
        start = data.index(unreleased_section) + len(unreleased_section)
        file.seek(start)
        file.write(f"\n\n## [{version_no}] - {date.today().isoformat()}")
        file.write(data[start:])
        file.truncate()

        # Add a link for the new version and update the unreleased link
        file.seek(0)
        data = file.read()
        start = data.index(unreleased_url_label) + len(unreleased_url_label)
        file.seek(start)
        file.write(unreleased_url.format(version=version_no))

        file.write(f"\n[{version_no}]: ")
        file.write(data[start:].replace("...HEAD", f"...v{version_no}"))
        file.truncate()

    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
