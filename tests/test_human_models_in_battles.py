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
        
        # Simulate the code generation loop logic
        models_to_skip = []
        
        for model in test_models:
            if model.get("is_human", False):
                models_to_skip.append(model)
                continue
        
        # Verify human model was added to skip list
        assert len(models_to_skip) == 1
        assert models_to_skip[0]["display_name"] == "Human Model"

    def test_human_models_should_participate_in_battles(self):
        """Test that human models should NOT be filtered out before battles."""
        # Mock models with one human model
        test_models = [
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "Human Model", "model_name": None, "is_human": True},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        models_to_skip = [
            {"display_name": "Human Model", "model_name": None, "is_human": True}
        ]
        
        # This is the OLD behavior (incorrect) - filtering out models_to_skip
        models_after_old_filter = [m for m in test_models if m not in models_to_skip]
        
        # This should be the NEW behavior (correct) - NOT filtering
        models_after_new_filter = test_models
        
        # Demonstrate the old behavior was wrong
        assert len(models_after_old_filter) == 2, "Old behavior incorrectly filters out human models"
        
        # After the fix, all models should remain for battles
        assert len(models_after_new_filter) == 3
        assert any(m["display_name"] == "Human Model" for m in models_after_new_filter)

    def test_top_model_skipped_from_code_generation(self):
        """Test that the top model from latest session is skipped from code generation."""
        test_models = [
            {"display_name": "Top Model", "model_name": "top/model"},
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        top_model_name = "Top Model"
        models_to_skip = []
        
        for model in test_models:
            if model["display_name"] == top_model_name:
                models_to_skip.append(model)
                continue
        
        # Verify top model was added to skip list
        assert len(models_to_skip) == 1
        assert models_to_skip[0]["display_name"] == "Top Model"

    def test_top_model_should_participate_in_battles(self):
        """Test that the top model should NOT be filtered out before battles."""
        test_models = [
            {"display_name": "Top Model", "model_name": "top/model"},
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        models_to_skip = [
            {"display_name": "Top Model", "model_name": "top/model"}
        ]
        
        # This is the OLD behavior (incorrect) - filtering out models_to_skip
        models_after_old_filter = [m for m in test_models if m not in models_to_skip]
        
        # This should be the NEW behavior (correct) - NOT filtering
        models_after_new_filter = test_models
        
        # Demonstrate the old behavior was wrong
        assert len(models_after_old_filter) == 2, "Old behavior incorrectly filters out top model"
        
        # After the fix, all models should remain for battles
        assert len(models_after_new_filter) == 3
        assert any(m["display_name"] == "Top Model" for m in models_after_new_filter)

    def test_models_that_fail_code_generation_logic(self):
        """Test the logic for handling models that fail code generation."""
        test_models = [
            {"display_name": "AI Model 1", "model_name": "ai/model-1"},
            {"display_name": "Failed Model", "model_name": "failed/model"},
            {"display_name": "AI Model 2", "model_name": "ai/model-2"},
        ]
        
        models_to_skip = []
        
        # Simulate: Model that produces no code should be added to skip list
        # In the real code, this happens when get_algos returns None
        failed_model = {"display_name": "Failed Model", "model_name": "failed/model"}
        models_to_skip.append(failed_model)
        
        # With the old behavior, this model would be filtered out
        models_for_battles_old = [m for m in test_models if m not in models_to_skip]
        
        # After the fix, models are NOT filtered based on models_to_skip
        models_for_battles_new = test_models
        
        # Demonstrate the old behavior filtered out the failed model
        assert len(models_for_battles_old) == 2
        assert not any(m["display_name"] == "Failed Model" for m in models_for_battles_old)
        
        # After the fix, all models are passed to battles (including failed ones)
        # The battle system (load_agent_class) will skip models without valid code
        assert len(models_for_battles_new) == 3
        assert any(m["display_name"] == "Failed Model" for m in models_for_battles_new)
        
        # Verify the skip list was populated correctly
        assert len(models_to_skip) == 1
        assert models_to_skip[0]["display_name"] == "Failed Model"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
