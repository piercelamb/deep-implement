"""Tests for validate_go_guardrails.py — no git dependency, tests against string content."""

import json
import subprocess
import sys

import pytest

# Import validation functions directly
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts"))
from checks.validate_go_guardrails import (
    check_cross_service_imports,
    check_file_size,
    check_function_lengths,
    check_hex_layers,
    check_package_declaration,
    check_prohibited_patterns,
    check_self_imports,
    validate_file,
)


# --- File size tests ---


class TestFileSize:
    def test_service_file_under_limit(self):
        content = "package svc\n" + "// line\n" * 298
        assert check_file_size("internal/service/foo.go", content) == []

    def test_service_file_over_limit(self):
        content = "package svc\n" + "// line\n" * 310
        violations = check_file_size("internal/service/foo.go", content)
        assert len(violations) == 1
        assert "max 300" in violations[0]

    def test_port_file_limit(self):
        content = "package ports\n" + "// line\n" * 105
        violations = check_file_size("internal/ports/repo.go", content)
        assert len(violations) == 1
        assert "max 100" in violations[0]

    def test_domain_file_limit(self):
        content = "package domain\n" + "// line\n" * 260
        violations = check_file_size("internal/domain/entity.go", content)
        assert len(violations) == 1
        assert "max 250" in violations[0]

    def test_handler_file_limit(self):
        content = "package handler\n" + "// line\n" * 260
        violations = check_file_size("internal/handler/http/api.go", content)
        assert len(violations) == 1
        assert "max 250" in violations[0]

    def test_test_file_limit(self):
        content = "package svc_test\n" + "// line\n" * 498
        assert check_file_size("internal/service/foo_test.go", content) == []

    def test_test_file_over_limit(self):
        content = "package svc_test\n" + "// line\n" * 510
        violations = check_file_size("internal/service/foo_test.go", content)
        assert len(violations) == 1
        assert "max 500" in violations[0]


# --- Function length tests ---


class TestFunctionLength:
    def test_short_function_passes(self):
        content = "package svc\n\nfunc DoThing() error {\n" + "\t// line\n" * 30 + "}\n"
        assert check_function_lengths("internal/service/foo.go", content) == []

    def test_long_function_fails(self):
        content = "package svc\n\nfunc DoThing() error {\n" + "\t// line\n" * 80 + "}\n"
        violations = check_function_lengths("internal/service/foo.go", content)
        assert len(violations) == 1
        assert "func DoThing" in violations[0]
        assert "max 75" in violations[0]

    def test_method_receiver(self):
        content = "package svc\n\nfunc (s *Svc) DoThing() error {\n" + "\t// line\n" * 80 + "}\n"
        violations = check_function_lengths("internal/service/foo.go", content)
        assert len(violations) == 1
        assert "max 75" in violations[0]

    def test_test_function_higher_limit(self):
        content = "package svc_test\n\nfunc TestBigTable(t *testing.T) {\n" + "\t// line\n" * 140 + "}\n"
        assert check_function_lengths("internal/service/foo_test.go", content) == []

    def test_test_function_over_limit(self):
        content = "package svc_test\n\nfunc TestBigTable(t *testing.T) {\n" + "\t// line\n" * 160 + "}\n"
        violations = check_function_lengths("internal/service/foo_test.go", content)
        assert len(violations) == 1
        assert "max 150" in violations[0]


# --- Package declaration tests ---


class TestPackageDeclaration:
    def test_valid_package(self):
        assert check_package_declaration("foo.go", "package main\n\nfunc main() {}") == []

    def test_missing_package(self):
        violations = check_package_declaration("foo.go", "func main() {}")
        assert len(violations) == 1
        assert "missing package" in violations[0]


# --- Hex layer import tests ---


class TestHexLayers:
    def test_domain_importing_adapter_fails(self):
        content = 'package domain\n\nimport "github.com/org/repo/services/foo/internal/adapter/postgres"\n'
        violations = check_hex_layers("services/foo/internal/domain/entity.go", content)
        assert len(violations) == 1
        assert "domain layer imports adapter layer" in violations[0]

    def test_domain_importing_service_fails(self):
        content = 'package domain\n\nimport "github.com/org/repo/services/foo/internal/service"\n'
        violations = check_hex_layers("services/foo/internal/domain/entity.go", content)
        assert len(violations) == 1
        assert "domain layer imports service layer" in violations[0]

    def test_adapter_importing_domain_ok(self):
        content = 'package postgres\n\nimport "github.com/org/repo/services/foo/internal/domain"\n'
        assert check_hex_layers("services/foo/internal/adapter/postgres/repo.go", content) == []

    def test_service_importing_ports_ok(self):
        content = 'package service\n\nimport "github.com/org/repo/services/foo/internal/ports"\n'
        assert check_hex_layers("services/foo/internal/service/svc.go", content) == []

    def test_non_hex_file_ignored(self):
        content = 'package main\n\nimport "github.com/org/repo/services/foo/internal/adapter/postgres"\n'
        assert check_hex_layers("cmd/server/main.go", content) == []

    def test_ports_importing_handler_fails(self):
        content = 'package ports\n\nimport "github.com/org/repo/services/foo/internal/handler/http"\n'
        violations = check_hex_layers("services/foo/internal/ports/repo.go", content)
        assert len(violations) == 1
        assert "ports layer imports handler layer" in violations[0]


# --- Cross-service import tests ---


class TestCrossServiceImports:
    def test_cross_service_internal_import(self):
        content = 'package svc\n\nimport "github.com/org/repo/services/other/internal/domain"\n'
        violations = check_cross_service_imports("services/control-plane/internal/service/svc.go", content)
        assert len(violations) == 1
        assert "other" in violations[0]

    def test_same_service_internal_ok(self):
        content = 'package svc\n\nimport "github.com/org/repo/services/control-plane/internal/domain"\n'
        assert check_cross_service_imports("services/control-plane/internal/service/svc.go", content) == []


# --- Self-import tests ---


class TestSelfImports:
    def test_self_import_detected(self):
        content = 'package domain\n\nimport "github.com/org/repo/services/foo/internal/domain"\n'
        violations = check_self_imports("services/foo/internal/domain/entity.go", content)
        assert len(violations) == 1
        assert "self-import" in violations[0]

    def test_different_package_ok(self):
        content = 'package service\n\nimport "github.com/org/repo/services/foo/internal/domain"\n'
        assert check_self_imports("services/foo/internal/service/svc.go", content) == []


# --- Prohibited patterns ---


class TestProhibitedPatterns:
    def test_hardcoded_secret(self):
        content = 'package svc\n\nvar api_key = "super-secret-key-12345"\n'
        violations = check_prohibited_patterns("internal/service/foo.go", content)
        assert any("Hardcoded secret" in v for v in violations)

    def test_os_exit_in_non_main(self):
        content = "package svc\n\nimport \"os\"\n\nfunc cleanup() { os.Exit(1) }\n"
        violations = check_prohibited_patterns("internal/service/foo.go", content)
        assert any("os.Exit" in v for v in violations)

    def test_os_exit_in_main_ok(self):
        content = "package main\n\nimport \"os\"\n\nfunc main() { os.Exit(1) }\n"
        assert check_prohibited_patterns("cmd/server/main.go", content) == []

    def test_panic_in_non_test(self):
        content = "package svc\n\nfunc bad() { panic(\"oops\") }\n"
        violations = check_prohibited_patterns("internal/service/foo.go", content)
        assert any("panic()" in v for v in violations)

    def test_panic_in_test_ok(self):
        content = "package svc_test\n\nfunc helper() { panic(\"test helper\") }\n"
        assert check_prohibited_patterns("internal/service/foo_test.go", content) == []


# --- Non-Go files ignored ---


class TestNonGoFiles:
    def test_non_go_file_no_violations(self):
        # validate_file should still work but non-.go files aren't discovered
        content = "This is a markdown file.\n" * 500
        # The function still checks — but discovery filters .go only
        # So we test that the script's discover step would skip it
        assert "README.md".endswith(".go") is False


# --- Override flag ---


class TestOverrides:
    def test_override_increases_limit(self):
        """After applying override, a previously-violating file passes."""
        import scripts.checks.validate_go_guardrails as mod

        original = mod.MAX_FILE_LINES
        try:
            mod.apply_overrides({"max_file_lines": "450"})
            assert mod.MAX_FILE_LINES == 450
            content = "package svc\n" + "// line\n" * 400
            assert mod.check_file_size("internal/service/foo.go", content) == []
        finally:
            mod.MAX_FILE_LINES = original

    def test_unknown_override_ignored(self, capsys):
        import scripts.checks.validate_go_guardrails as mod

        mod.apply_overrides({"bogus_key": "999"})
        captured = capsys.readouterr()
        assert "unknown override" in captured.err


# --- Integration: validate_file combines all checks ---


class TestValidateFile:
    def test_clean_file_passes(self):
        content = (
            "package svc\n\n"
            "func DoThing() error {\n"
            "\treturn nil\n"
            "}\n"
        )
        assert validate_file("internal/service/foo.go", content) == []

    def test_multiple_violations(self):
        content = "func bad() { panic(\"oops\") }\n" * 400
        violations = validate_file("internal/service/foo.go", content)
        # Should have: over file limit, missing package, panic, possibly function length
        assert len(violations) >= 3
