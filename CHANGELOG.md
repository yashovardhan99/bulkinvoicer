# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-08-22

### Changed

- Add multiprocessing for individual PDF generation.
- Add multiprocessing for client PDF generation.
- Cache generated QR code to allow re-use.

### Remove

- Remove clients with no transactions and zero-balance from client-wise summary.

## [0.1.0] - 2025-08-17

### Changed

- Update most fonts to subset to reduce distribution size.

### Fixed

- Add tag check to release workflow to prevent change with an existing tag.

### Removed

- Unused python script for generating invoice PDF (`invoice.py`)

## [0.1.0a0] - 2025-08-16

### Added

- Start Changelog file for easy tracking.
- Add validations for config.toml file (using pydantic)

### Changed

- Update Readme to include Pypi release information.
- Refactor usage of config from dictionary to class objects.

## [0.1.0.dev1] - 2025-08-15

### Added

- Initial release of BulkInvoicer.
- Sample files and configuration.
- README and other related files.

[unreleased]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0a0...v0.1.0
[0.1.0a0]: https://github.com/yashovardhan99/bulkinvoicer/compare/v0.1.0.dev1...v0.1.0a0
[0.1.0.dev1]: https://github.com/yashovardhan99/bulkinvoicer/commits/v0.1.0.dev1