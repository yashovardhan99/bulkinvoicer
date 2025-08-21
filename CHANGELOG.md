# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Add multiprocessing for individual PDF generation.
- Add multiprocessing for client PDF generation.
- Cache generated QR code to allow re-use.

## [0.1.0]

### Changed

- Update most fonts to subset to reduce distribution size.

### Fixed

- Add tag check to release workflow to prevent change with an existing tag.

### Removed

- Unused python script for generating invoice PDF (`invoice.py`)

## [0.1.0a0]

### Added

- Start Changelog file for easy tracking.
- Add validations for config.toml file (using pydantic)

### Changed

- Update Readme to include Pypi release information.
- Refactor usage of config from dictionary to class objects.

## [0.1.0.dev1]

### Added

- Initial release of BulkInvoicer.
- Sample files and configuration.
- README and other related files.

[unreleased]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0...HEAD
[v0.1.0]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0a0...v0.1.0
[v0.1.0a0]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0.dev1...v0.1.0a0
[0.1.0.dev1]: https://github.com/yashovardhan99/bulkinvoicer/commits/v0.1.0.dev1