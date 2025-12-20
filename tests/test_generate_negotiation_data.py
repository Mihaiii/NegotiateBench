import sys
from pathlib import Path

import pytest

# Add parent directory to path so we can import from misc
sys.path.insert(0, str(Path(__file__).parent.parent))

from misc.battlefield import generate_negotiation_data


class TestGenerateNegotiationData:
    """Tests for the generate_negotiation_data function."""

    def test_default_generates_20_scenarios(self, monkeypatch):
        """Test that default MAX_NUM_DATA generates up to 20 scenarios."""
        monkeypatch.delenv("MAX_NUM_DATA", raising=False)

        data = generate_negotiation_data()

        assert len(data) <= 20
        assert len(data) > 0

    def test_max_num_data_1(self, monkeypatch):
        """Test with MAX_NUM_DATA=1."""
        monkeypatch.setenv("MAX_NUM_DATA", "1")

        data = generate_negotiation_data()

        assert len(data) <= 1

    def test_max_num_data_5(self, monkeypatch):
        """Test with MAX_NUM_DATA=5."""
        monkeypatch.setenv("MAX_NUM_DATA", "5")

        data = generate_negotiation_data()

        assert len(data) <= 5
        assert len(data) > 0

    def test_max_num_data_10(self, monkeypatch):
        """Test with MAX_NUM_DATA=10."""
        monkeypatch.setenv("MAX_NUM_DATA", "10")

        data = generate_negotiation_data()

        assert len(data) <= 10
        assert len(data) > 0

    def test_max_num_data_50(self, monkeypatch):
        """Test with larger MAX_NUM_DATA=50."""
        monkeypatch.setenv("MAX_NUM_DATA", "50")

        data = generate_negotiation_data()

        assert len(data) <= 50
        assert len(data) > 0

    def test_invalid_max_num_data_uses_default(self, monkeypatch):
        """Test that invalid MAX_NUM_DATA falls back to default 20."""
        monkeypatch.setenv("MAX_NUM_DATA", "invalid")

        data = generate_negotiation_data()

        assert len(data) <= 20

    def test_scenario_has_required_keys(self, monkeypatch):
        """Test that each scenario has all required keys."""
        monkeypatch.setenv("MAX_NUM_DATA", "5")

        data = generate_negotiation_data()

        for scenario in data:
            assert "counts" in scenario
            assert "player_0" in scenario
            assert "player_1" in scenario
            assert "rounds" in scenario

    def test_counts_and_values_same_length(self, monkeypatch):
        """Test that counts and player values have the same length."""
        monkeypatch.setenv("MAX_NUM_DATA", "10")

        data = generate_negotiation_data()

        for scenario in data:
            counts_len = len(scenario["counts"])
            assert len(scenario["player_0"]) == counts_len
            assert len(scenario["player_1"]) == counts_len

    def test_counts_length_between_2_and_10(self, monkeypatch):
        """Test that counts length is between 2 and 10."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            assert 2 <= len(scenario["counts"]) <= 10

    def test_counts_values_between_1_and_5(self, monkeypatch):
        """Test that count values are between 1 and 5."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            for count in scenario["counts"]:
                assert 1 <= count <= 5

    def test_player_values_between_0_and_10(self, monkeypatch):
        """Test that player values are between 0 and 10."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            for value in scenario["player_0"]:
                assert 0 <= value <= 10
            for value in scenario["player_1"]:
                assert 0 <= value <= 10

    def test_total_worth_is_valid(self, monkeypatch):
        """Test that total worth (counts * values) is 32, 64, or 128."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")
        valid_worths = {32, 64, 128}

        data = generate_negotiation_data()

        for scenario in data:
            counts = scenario["counts"]
            player_0 = scenario["player_0"]
            player_1 = scenario["player_1"]

            total_0 = sum(c * v for c, v in zip(counts, player_0))
            total_1 = sum(c * v for c, v in zip(counts, player_1))

            assert (
                total_0 in valid_worths
            ), f"Player 0 total {total_0} not in {valid_worths}"
            assert (
                total_1 in valid_worths
            ), f"Player 1 total {total_1} not in {valid_worths}"

    def test_both_players_have_same_total_worth(self, monkeypatch):
        """Test that both players have the same total worth."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            counts = scenario["counts"]
            player_0 = scenario["player_0"]
            player_1 = scenario["player_1"]

            total_0 = sum(c * v for c, v in zip(counts, player_0))
            total_1 = sum(c * v for c, v in zip(counts, player_1))

            assert total_0 == total_1

    def test_rounds_based_on_target_worth(self, monkeypatch):
        """Test that rounds = target_worth // 4."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            counts = scenario["counts"]
            player_0 = scenario["player_0"]

            total_worth = sum(c * v for c, v in zip(counts, player_0))
            expected_rounds = total_worth // 4

            assert scenario["rounds"] == expected_rounds

    def test_rounds_valid_values(self, monkeypatch):
        """Test that rounds are 8, 16, or 32 (corresponding to worths 32, 64, 128)."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")
        valid_rounds = {8, 16, 32}

        data = generate_negotiation_data()

        for scenario in data:
            assert scenario["rounds"] in valid_rounds

    def test_less_than_half_values_are_zero(self, monkeypatch):
        """Test that less than half of the values are zeros for each player."""
        monkeypatch.setenv("MAX_NUM_DATA", "20")

        data = generate_negotiation_data()

        for scenario in data:
            player_0 = scenario["player_0"]
            player_1 = scenario["player_1"]

            zero_count_0 = sum(1 for v in player_0 if v == 0)
            zero_count_1 = sum(1 for v in player_1 if v == 0)

            assert (
                zero_count_0 < len(player_0) / 2
            ), f"Player 0 has too many zeros: {zero_count_0}/{len(player_0)}"
            assert (
                zero_count_1 < len(player_1) / 2
            ), f"Player 1 has too many zeros: {zero_count_1}/{len(player_1)}"

    def test_generates_different_scenarios(self, monkeypatch):
        """Test that multiple calls generate different scenarios (randomness check)."""
        monkeypatch.setenv("MAX_NUM_DATA", "5")

        data1 = generate_negotiation_data()
        data2 = generate_negotiation_data()

        # Convert to comparable format
        str1 = str(data1)
        str2 = str(data2)

        # They should be different (with very high probability)
        # Note: There's a tiny chance this could fail due to randomness
        assert str1 != str2 or len(data1) == 0

    def test_empty_result_with_zero_max_num_data(self, monkeypatch):
        """Test with MAX_NUM_DATA=0."""
        monkeypatch.setenv("MAX_NUM_DATA", "0")

        data = generate_negotiation_data()

        assert len(data) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
