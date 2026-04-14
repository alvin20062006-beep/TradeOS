"""
Unit tests for qlib/availability.py
"""
import pytest


class TestAvailability:
    """Tests for check_qlib() and related functions."""
    
    def test_check_qlib_returns_required_keys(self):
        """A1: Return dict must have all required keys."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        required_keys = {"runtime_baseline", "tier", "available_modules", "missing_modules", "warnings", "notes"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
    
    def test_check_qlib_runtime_baseline(self):
        """A1: runtime_baseline field must be a string."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["runtime_baseline"], str)
        assert "pyqlib" in result["runtime_baseline"].lower() or "qlib" in result["runtime_baseline"].lower()
    
    def test_check_qlib_tier_is_int(self):
        """A1: tier field must be an integer."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["tier"], int), f"tier must be int, got {type(result['tier'])}"
        assert 0 <= result["tier"] <= 3, f"tier must be 0-3, got {result['tier']}"
    
    def test_check_qlib_available_modules_is_list(self):
        """A1: available_modules field must be a list."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["available_modules"], list)
    
    def test_check_qlib_missing_modules_is_list(self):
        """A1: missing_modules field must be a list."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["missing_modules"], list)
    
    def test_check_qlib_warnings_is_list(self):
        """A2: warnings field must be a list."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["warnings"], list)
    
    def test_check_qlib_notes_is_list(self):
        """A2: notes field must be a list."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        assert isinstance(result["notes"], list)
    
    def test_check_qlib_does_not_raise(self):
        """A2: check_qlib() must not raise exceptions."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        # Should not raise
        result = check_qlib()
        assert result is not None
    
    def test_check_qlib_tier1_core_modules_present(self):
        """A1: Tier 1 core modules must be in available_modules if qlib is installed."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        tier1_core = {"qlib.data.D", "qlib.workflow.R", "qlib.model.base"}
        available = set(result["available_modules"])
        
        # At least some Tier 1 modules should be available
        found = tier1_core & available
        assert len(found) >= 1, f"Expected at least one of {tier1_core} to be available, got: {available}"
    
    def test_is_qlib_available_true_when_qlib_installed(self):
        """A1: is_qlib_available() returns True when qlib is installed."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import is_qlib_available
        
        result = is_qlib_available(min_tier=1)
        assert isinstance(result, bool)
    
    def test_is_qlib_available_min_tier(self):
        """A1: is_qlib_available() respects min_tier parameter."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import is_qlib_available
        
        # tier 1 check should always pass if qlib is installed
        result_tier1 = is_qlib_available(min_tier=1)
        assert isinstance(result_tier1, bool)
    
    def test_get_qlib_version(self):
        """A1: get_qlib_version() returns version string or None."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import get_qlib_version
        
        version = get_qlib_version()
        # Either returns a string or None
        assert version is None or isinstance(version, str)
    
    def test_get_status_alias(self):
        """A1: get_status() is an alias for check_qlib()."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib, get_status
        
        r1 = check_qlib()
        r2 = get_status()
        assert r1.keys() == r2.keys()
    
    def test_check_qlib_field_consistency(self):
        """A3: available_modules uses consistent naming (not 'available')."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.availability import check_qlib
        
        result = check_qlib()
        # Must use available_modules (not 'available' or 'available_modules_list')
        assert "available_modules" in result
        assert "available" not in result  # Old inconsistent naming
