"""Tests for multi-provider support."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path so we can import from job
sys.path.insert(0, str(Path(__file__).parent.parent))

from misc.io import load_models


class TestProviderSupport:
    """Tests for multi-provider support in models.yaml."""

    def test_models_yaml_loads_correctly(self):
        """Test that models.yaml loads and contains expected models."""
        models = load_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        
        # Check that we have models from both providers
        openrouter_models = [m for m in models if m.get("provider", "openrouter") == "openrouter"]
        aihubmix_models = [m for m in models if m.get("provider") == "aihubmix"]
        human_models = [m for m in models if m.get("is_human", False)]
        
        assert len(openrouter_models) > 0, "Should have OpenRouter models"
        assert len(aihubmix_models) > 0, "Should have AIHubMix models"
        assert len(human_models) > 0, "Should have human models"

    def test_openrouter_models_have_openrouter_name(self):
        """Test that OpenRouter models have openrouter_name field."""
        models = load_models()
        openrouter_models = [m for m in models if m.get("provider", "openrouter") == "openrouter" and not m.get("is_human")]
        
        for model in openrouter_models:
            assert "openrouter_name" in model, f"Model {model['display_name']} should have openrouter_name"
            assert model["openrouter_name"], f"Model {model['display_name']} openrouter_name should not be empty"

    def test_aihubmix_models_have_model_name_and_provider(self):
        """Test that AIHubMix models have model_name and provider fields."""
        models = load_models()
        aihubmix_models = [m for m in models if m.get("provider") == "aihubmix"]
        
        for model in aihubmix_models:
            assert "model_name" in model, f"Model {model['display_name']} should have model_name"
            assert model["model_name"], f"Model {model['display_name']} model_name should not be empty"
            assert model["provider"] == "aihubmix", f"Model {model['display_name']} should have provider=aihubmix"

    def test_all_models_have_display_name(self):
        """Test that all models have display_name."""
        models = load_models()
        
        for model in models:
            assert "display_name" in model, "All models should have display_name"
            assert model["display_name"], "display_name should not be empty"

    def test_specific_aihubmix_models_present(self):
        """Test that specific AIHubMix models are present."""
        models = load_models()
        model_names = {m["display_name"] for m in models}
        
        expected_aihubmix = {
            "Doubao Seed 2.0 Pro",
            "Coding GLM 5",
            "Doubao Seed 2.0 Code Preview"
        }
        
        for name in expected_aihubmix:
            assert name in model_names, f"Model {name} should be in models.yaml"

    def test_specific_openrouter_models_present(self):
        """Test that specific new OpenRouter models are present."""
        models = load_models()
        model_names = {m["display_name"] for m in models}
        
        expected_openrouter = {
            "MiniMax M2.5",
            "GLM 5",
            "Qwen 3 Max Thinking",
            "Claude Opus 4.6",
            "Qwen 3 Coder Next",
            "Kimi K2.5"
        }
        
        for name in expected_openrouter:
            assert name in model_names, f"Model {name} should be in models.yaml"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
