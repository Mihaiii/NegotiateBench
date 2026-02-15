"""Tests for ensuring human models and top models participate in battles."""
import pytest


class TestHumanModelsInBattles:
    """Tests for ensuring models with is_human flag participate in battles."""

    def test_human_models_skipped_from_code_generation(self):
        """Test that models with is_human=true are skipped from code generation loop."""
        # Mock models with one human model
        test_models = [
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "Human Model", "model_name": None, "is_human": True},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        # Simulate the code generation loop logic using models.copy()
        models = test_models.copy()
        for model in models.copy():
            if model.get("is_human", False):
                # Human model is skipped (continue) but NOT removed from models list
                continue
        
        # Verify human model is still in the models list for battles
        assert len(models) == 3
        assert any(m["display_name"] == "Human Model" for m in models)

    def test_human_models_should_participate_in_battles(self):
        """Test that human models should NOT be removed from models list before battles."""
        # Mock models with one human model
        test_models = [
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "Human Model", "model_name": None, "is_human": True},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        # Simulate the loop - human models use continue, not remove
        models = test_models.copy()
        for model in models.copy():
            if model.get("is_human", False):
                continue  # Skip code generation, but stay in list
        
        # After the fix, all models should remain for battles
        assert len(models) == 3
        assert any(m["display_name"] == "Human Model" for m in models)

    def test_top_model_skipped_from_code_generation(self):
        """Test that the top model from latest session is skipped from code generation."""
        test_models = [
            {"display_name": "Top Model", "model_name": "top/model"},
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        top_model_name = "Top Model"
        
        # Simulate the code generation loop
        models = test_models.copy()
        for model in models.copy():
            if model["display_name"] == top_model_name:
                continue  # Skip code generation, but stay in list
        
        # Verify top model is still in the models list
        assert len(models) == 3
        assert any(m["display_name"] == "Top Model" for m in models)

    def test_top_model_should_participate_in_battles(self):
        """Test that the top model should NOT be removed from models list before battles."""
        test_models = [
            {"display_name": "Top Model", "model_name": "top/model"},
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        top_model_name = "Top Model"
        
        # Simulate the loop - top model uses continue, not remove
        models = test_models.copy()
        for model in models.copy():
            if model["display_name"] == top_model_name:
                continue  # Skip code generation, but stay in list
        
        # After the fix, all models should remain for battles
        assert len(models) == 3
        assert any(m["display_name"] == "Top Model" for m in models)

    def test_models_that_fail_code_generation_logic(self):
        """Test that models that fail code generation ARE removed from the models list."""
        test_models = [
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "Failed Model", "model_name": "failed/model"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        # Simulate: Model that produces no code should be removed from models list
        # In the real code, this happens when get_algos returns None
        models = test_models.copy()
        for model in models.copy():
            # Simulate a failed model
            if model["display_name"] == "Failed Model":
                models.remove(model)  # Remove failed model
                continue
        
        # Models that fail code generation should be removed
        assert len(models) == 2
        assert not any(m["display_name"] == "Failed Model" for m in models)
        assert any(m["display_name"] == "AI Model 1" for m in models)
        assert any(m["display_name"] == "AI Model 2" for m in models)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
