# Changelog

All notable changes to deep-implement will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-01-30

### Changed
- **Unified session ID** - Changed `DEEP_IMPLEMENT_SESSION_ID` to shared `DEEP_SESSION_ID`
- **Normalized env var** - Changed `CLAUDE_SESSION_ID` to `DEEP_SESSION_ID` in env file writes and all scripts
- SessionStart hook now checks if `DEEP_SESSION_ID` already matches before outputting
- Prevents duplicate output when multiple deep-* plugins run together

## [0.1.0] - 2025-01-01

### Added
- Initial release
- Section-by-section implementation workflow from /deep-plan output
- TDD methodology with code review at each step
- Git commits with review trails
- SessionStart hook for session ID capture
