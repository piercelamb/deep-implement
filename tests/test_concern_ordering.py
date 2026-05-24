"""Tests for concern-type ordering functions in sections.py."""

import pytest

from scripts.lib.sections import (
    parse_manifest_block,
    parse_section_concerns,
    parse_section_meta,
    sort_sections_by_concern,
)


class TestParseManifestBlockWithConcernTags:
    """Verify parse_manifest_block ignores concern tags (backward compat)."""

    def test_manifest_with_concern_tags_returns_bare_names(self):
        """Tags should be stripped — only section names returned."""
        content = """<!-- SECTION_MANIFEST
section-01-foundation scaffold
section-02-models functional
section-03-api functional
END_MANIFEST -->"""
        result = parse_manifest_block(content)
        assert result == [
            "section-01-foundation",
            "section-02-models",
            "section-03-api",
        ]

    def test_manifest_mixed_tagged_and_bare(self):
        """Lines with and without tags both parse correctly."""
        content = """<!-- SECTION_MANIFEST
section-01-foundation scaffold
section-02-models
section-03-api functional
END_MANIFEST -->"""
        result = parse_manifest_block(content)
        assert result == [
            "section-01-foundation",
            "section-02-models",
            "section-03-api",
        ]


class TestParseSectionConcerns:
    """Tests for parse_section_concerns()."""

    def test_with_tags(self):
        content = """<!-- SECTION_MANIFEST
section-01-foundation scaffold
section-02-models functional
section-03-logging observability
END_MANIFEST -->"""
        result = parse_section_concerns(content)
        assert result == {
            "section-01-foundation": "scaffold",
            "section-02-models": "functional",
            "section-03-logging": "observability",
        }

    def test_no_tags(self):
        content = """<!-- SECTION_MANIFEST
section-01-foundation
section-02-models
END_MANIFEST -->"""
        result = parse_section_concerns(content)
        assert result == {}

    def test_mixed_tags(self):
        content = """<!-- SECTION_MANIFEST
section-01-foundation scaffold
section-02-models
section-03-api functional
END_MANIFEST -->"""
        result = parse_section_concerns(content)
        assert result == {
            "section-01-foundation": "scaffold",
            "section-03-api": "functional",
        }

    def test_invalid_tag_ignored(self):
        content = """<!-- SECTION_MANIFEST
section-01-foundation scaffold
section-02-models invalid_concern
section-03-api functional
END_MANIFEST -->"""
        result = parse_section_concerns(content)
        assert result == {
            "section-01-foundation": "scaffold",
            "section-03-api": "functional",
        }
        assert "section-02-models" not in result

    def test_no_manifest_block(self):
        content = "# Just a regular file"
        result = parse_section_concerns(content)
        assert result == {}

    def test_all_concern_types(self):
        content = """<!-- SECTION_MANIFEST
section-01-init scaffold
section-02-core functional
section-03-logging observability
section-04-config configuration
section-05-errors resilience
section-06-wiring integration
END_MANIFEST -->"""
        result = parse_section_concerns(content)
        assert len(result) == 6
        assert result["section-04-config"] == "configuration"
        assert result["section-05-errors"] == "resilience"
        assert result["section-06-wiring"] == "integration"


class TestSortSectionsByConcern:
    """Tests for sort_sections_by_concern()."""

    def test_reorders_by_concern(self):
        sections = [
            "section-01-api",        # functional
            "section-02-init",       # scaffold
            "section-03-logging",    # observability
        ]
        concerns = {
            "section-01-api": "functional",
            "section-02-init": "scaffold",
            "section-03-logging": "observability",
        }
        result = sort_sections_by_concern(sections, concerns)
        assert result == [
            "section-02-init",       # scaffold first
            "section-01-api",        # functional second
            "section-03-logging",    # observability third
        ]

    def test_preserves_number_order_within_concern(self):
        sections = [
            "section-01-ports",
            "section-02-domain",
            "section-03-service",
        ]
        concerns = {
            "section-01-ports": "functional",
            "section-02-domain": "functional",
            "section-03-service": "functional",
        }
        result = sort_sections_by_concern(sections, concerns)
        # All functional — original order preserved
        assert result == sections

    def test_untagged_sections_last(self):
        sections = [
            "section-01-api",
            "section-02-init",
            "section-03-misc",
        ]
        concerns = {
            "section-01-api": "functional",
            "section-02-init": "scaffold",
        }
        result = sort_sections_by_concern(sections, concerns)
        assert result == [
            "section-02-init",   # scaffold
            "section-01-api",    # functional
            "section-03-misc",   # untagged last
        ]

    def test_empty_concerns_returns_original(self):
        sections = ["section-01-a", "section-02-b", "section-03-c"]
        result = sort_sections_by_concern(sections, {})
        assert result == sections

    def test_full_concern_ordering(self):
        sections = [
            "section-01-wiring",
            "section-02-errors",
            "section-03-config",
            "section-04-logging",
            "section-05-core",
            "section-06-init",
        ]
        concerns = {
            "section-01-wiring": "integration",
            "section-02-errors": "resilience",
            "section-03-config": "configuration",
            "section-04-logging": "observability",
            "section-05-core": "functional",
            "section-06-init": "scaffold",
        }
        result = sort_sections_by_concern(sections, concerns)
        assert result == [
            "section-06-init",     # scaffold
            "section-05-core",     # functional
            "section-04-logging",  # observability
            "section-03-config",   # configuration
            "section-02-errors",   # resilience
            "section-01-wiring",   # integration
        ]


class TestParseSectionMeta:
    """Tests for parse_section_meta()."""

    def test_parses_full_meta(self):
        content = """# Section 01: Foundation

<!-- SECTION_META
concern: scaffold
target_files: internal/ports/repository.go, internal/domain/entity.go
estimated_lines: 150
END_SECTION_META -->

## Implementation
Create the base structure.
"""
        result = parse_section_meta(content)
        assert result["concern"] == "scaffold"
        assert "internal/ports/repository.go" in result["target_files"]
        assert result["estimated_lines"] == "150"

    def test_missing_meta_returns_empty(self):
        content = """# Section 01: Foundation

## Implementation
Create the base structure.
"""
        result = parse_section_meta(content)
        assert result == {}

    def test_partial_meta(self):
        content = """<!-- SECTION_META
concern: functional
END_SECTION_META -->

# Content here
"""
        result = parse_section_meta(content)
        assert result == {"concern": "functional"}
        assert "target_files" not in result
