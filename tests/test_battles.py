import json
import sys
from pathlib import Path

import pytest
import yaml

# Add parent directory to path so we can import from misc
sys.path.insert(0, str(Path(__file__).parent.parent))

from misc.battlefield import generate_negotiation_data, run_battles


class TestBattles:
    """Tests for the negotiation battle system."""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Setup test environment variables and paths."""
        monkeypatch.setenv("MAX_SCENARIO_DATA", "10")
        monkeypatch.setenv("NUM_SAMPLES", "4")

        # Store original solutions path lookup
        self.test_dir = Path(__file__).parent
        self.solutions_dir = self.test_dir / "solutions"

    def load_test_models(self):
        """Load models from the test models2.yaml file."""
        config_path = self.test_dir / "models2.yaml"
        with open(config_path, "r") as f:
            return yaml.safe_load(f).get("models", [])

    def test_generate_negotiation_data(self):
        """Test that negotiation data is generated correctly."""
        data, total_target_worth = generate_negotiation_data()

        assert len(data) > 0
        assert len(data) <= 10  # MAX_SCENARIO_DATA is set to 10
        assert total_target_worth > 0

        for scenario in data:
            assert "counts" in scenario
            assert "player_0" in scenario
            assert "player_1" in scenario
            assert "rounds" in scenario

            # Verify counts and values have the same length
            assert len(scenario["counts"]) == len(scenario["player_0"])
            assert len(scenario["counts"]) == len(scenario["player_1"])

    def test_run_battles_returns_correct_structure(self, monkeypatch):
        """Test that run_battles returns the expected structure."""
        # Patch the solutions path in battlefield.py to use test solutions
        from misc import battlefield

        original_load_agent = battlefield.load_agent_class

        def patched_load_agent(display_name: str):
            solutions_path = self.solutions_dir / f"{display_name}.py"
            if not solutions_path.exists():
                return None
            try:
                with open(solutions_path, "r") as f:
                    code = f.read()
                namespace = {}
                exec(code, namespace)
                if "Agent" not in namespace:
                    return None
                return namespace["Agent"]
            except Exception as e:
                print(f"Failed to load agent for {display_name}: {e}")
                return None

        monkeypatch.setattr(battlefield, "load_agent_class", patched_load_agent)

        models = self.load_test_models()
        data, total_target_worth = generate_negotiation_data()

        battle_results, battle_scenarios = run_battles(models, data)

        # Check battle_results structure
        assert isinstance(battle_results, dict)
        for model_name, stats in battle_results.items():
            assert "total_profit" in stats
            assert isinstance(stats["total_profit"], (int, float))

        # Check battle_scenarios structure
        assert isinstance(battle_scenarios, dict)
        for key, scenarios in battle_scenarios.items():
            assert isinstance(key, tuple)
            assert len(key) == 2
            model_x, model_y = key
            assert isinstance(scenarios, list)

            for scenario in scenarios:
                assert "scenario" in scenario
                assert "outcome" in scenario
                assert f"{model_x}_profit" in scenario
                assert f"{model_y}_profit" in scenario
                assert "turn_history" in scenario

    def test_battle_scenarios_respects_num_samples(self, monkeypatch):
        """Test that battle_scenarios respects NUM_SAMPLES limit."""
        from misc import battlefield

        def patched_load_agent(display_name: str):
            solutions_path = self.solutions_dir / f"{display_name}.py"
            if not solutions_path.exists():
                return None
            try:
                with open(solutions_path, "r") as f:
                    code = f.read()
                namespace = {}
                exec(code, namespace)
                if "Agent" not in namespace:
                    return None
                return namespace["Agent"]
            except Exception as e:
                print(f"Failed to load agent for {display_name}: {e}")
                return None

        monkeypatch.setattr(battlefield, "load_agent_class", patched_load_agent)

        # Set NUM_SAMPLES to 4
        monkeypatch.setenv("NUM_SAMPLES", "4")

        models = self.load_test_models()
        data, total_target_worth = generate_negotiation_data()

        battle_results, battle_scenarios = run_battles(models, data)

        # Each pair should have at most NUM_SAMPLES scenarios
        for key, scenarios in battle_scenarios.items():
            assert len(scenarios) <= 4

    def test_turn_history_structure(self, monkeypatch):
        """Test that turn_history has the correct structure."""
        from misc import battlefield

        def patched_load_agent(display_name: str):
            solutions_path = self.solutions_dir / f"{display_name}.py"
            if not solutions_path.exists():
                return None
            try:
                with open(solutions_path, "r") as f:
                    code = f.read()
                namespace = {}
                exec(code, namespace)
                if "Agent" not in namespace:
                    return None
                return namespace["Agent"]
            except Exception as e:
                print(f"Failed to load agent for {display_name}: {e}")
                return None

        monkeypatch.setattr(battlefield, "load_agent_class", patched_load_agent)

        models = self.load_test_models()
        data, total_target_worth = generate_negotiation_data()

        battle_results, battle_scenarios = run_battles(models, data)

        for key, scenarios in battle_scenarios.items():
            model_x, model_y = key
            for scenario in scenarios:
                turn_history = scenario["turn_history"]
                assert isinstance(turn_history, list)

                for turn in turn_history:
                    assert "round" in turn
                    assert f"{model_x}_offer" in turn
                    assert f"{model_y}_offer" in turn
                    assert isinstance(turn["round"], int)

    def test_battle_scenarios_json_serializable(self, monkeypatch):
        """Test that battle_scenarios can be serialized to JSON."""
        from misc import battlefield

        def patched_load_agent(display_name: str):
            solutions_path = self.solutions_dir / f"{display_name}.py"
            if not solutions_path.exists():
                return None
            try:
                with open(solutions_path, "r") as f:
                    code = f.read()
                namespace = {}
                exec(code, namespace)
                if "Agent" not in namespace:
                    return None
                return namespace["Agent"]
            except Exception as e:
                print(f"Failed to load agent for {display_name}: {e}")
                return None

        monkeypatch.setattr(battlefield, "load_agent_class", patched_load_agent)

        models = self.load_test_models()
        data, total_target_worth = generate_negotiation_data()

        battle_results, battle_scenarios = run_battles(models, data)

        # Convert tuple keys to strings for JSON serialization
        battle_scenarios_json = {
            f"{k[0]} vs {k[1]}": v for k, v in battle_scenarios.items()
        }

        # Should not raise an exception
        json_str = json.dumps(battle_scenarios_json)
        assert isinstance(json_str, str)

        # Should be able to parse it back
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
