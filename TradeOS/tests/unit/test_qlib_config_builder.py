"""
Unit tests for qlib/config_builder.py
"""
import pytest
import tempfile
from pathlib import Path


class TestQlibConfigBuilder:
    """Tests for QlibConfigBuilder."""
    
    def test_build_cn_config(self):
        """A4: build() generates valid kwargs for region='cn'."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        config = builder.build()
        
        assert "region" in config
        assert config["region"] == "cn"
        assert "mount_path" in config
        assert "cn_data" in config["mount_path"] or "qlib_data" in config["mount_path"]
    
    def test_build_us_config(self):
        """A4/A5: build() generates valid kwargs for region='us'."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="us")
        config = builder.build()
        
        assert "region" in config
        assert config["region"] == "us"
        assert "mount_path" in config
        assert "us_data" in config["mount_path"] or "qlib_data" in config["mount_path"]
    
    def test_cn_and_us_different(self):
        """A5: CN and US regions produce different mount_path."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        cn = QlibConfigBuilder(region="cn").build()
        us = QlibConfigBuilder(region="us").build()
        
        assert cn["mount_path"] != us["mount_path"], "CN and US must have different mount paths"
    
    def test_build_has_provider(self):
        """A4: config has provider field."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        config = builder.build()
        
        assert "provider" in config
        assert isinstance(config["provider"], str)
    
    def test_build_has_auto_mount(self):
        """A4: config has auto_mount field."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        config = builder.build()
        
        assert "auto_mount" in config
    
    def test_custom_provider(self):
        """A4: custom provider overrides default."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn", provider="parquet")
        config = builder.build()
        
        assert config["provider"] == "parquet"
    
    def test_custom_mount_path(self):
        """A4: custom mount_path overrides region default."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn", mount_path="C:/custom/path")
        config = builder.build()
        
        assert config["mount_path"] == "C:/custom/path"
    
    def test_build_config_convenience_function(self):
        """A4: build_config() convenience function works."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import build_config
        
        config = build_config(region="cn")
        assert isinstance(config, dict)
        assert "region" in config
        assert "mount_path" in config
    
    def test_unknown_region_raises(self):
        """A5: unknown region raises ValueError."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        with pytest.raises(ValueError):
            QlibConfigBuilder(region="unknown")
    
    def test_to_yaml(self):
        """A6: to_yaml() saves a valid YAML file."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "test_config.yaml"
            saved = builder.to_yaml(yaml_path)
            
            assert saved.exists()
            
            # Verify YAML is readable
            import yaml
            with open(saved, "r") as f:
                loaded = yaml.safe_load(f)
            
            assert loaded["region"] == "cn"
            assert "mount_path" in loaded
    
    def test_from_yaml(self):
        """A6: from_yaml() loads config correctly."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "test_config.yaml"
            
            # Create and save
            original = QlibConfigBuilder(region="us", provider="parquet")
            original.to_yaml(yaml_path)
            
            # Load back
            loaded = QlibConfigBuilder.from_yaml(yaml_path)
            
            assert loaded.region == "us"
            assert loaded.provider == "parquet"
    
    def test_from_region_convenience(self):
        """A4: from_region() creates builder with defaults."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder.from_region("cn")
        assert builder.region == "cn"
        assert builder.provider == "csv"  # default
    
    def test_get_data_path(self):
        """A4: get_data_path() returns Path object."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        data_path = builder.get_data_path()
        
        assert isinstance(data_path, Path)
        assert "qlib_data" in str(data_path)
    
    def test_auto_mount_default_true(self):
        """A4: auto_mount defaults to True."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn")
        assert builder.auto_mount is True
        
        config = builder.build()
        assert config["auto_mount"] is True
    
    def test_auto_mount_false(self):
        """A4: auto_mount can be set to False."""
        import sys
        sys.path.insert(0, "C:/Users/hutia/.qclaw/workspace/ai-trading-tool")
        from core.research.qlib.config_builder import QlibConfigBuilder
        
        builder = QlibConfigBuilder(region="cn", auto_mount=False)
        config = builder.build()
        
        assert config["auto_mount"] is False
