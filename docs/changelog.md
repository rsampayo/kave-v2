# Changelog

## [Unreleased]

### Changed
- Refactored the duplicate `get_db` functions by centralizing in `app/db/session.py` and having `app/api/v1/deps/database.py` import from there, reducing code duplication while maintaining backward compatibility. 