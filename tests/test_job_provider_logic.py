"""Tests for job.py provider logic."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path so we can import from job
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestJobProviderLogic:
    """Tests for job.py provider logic."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up test environment variables."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test_key")
        monkeypatch.setenv("AIHUBMIX_API_KEY", "test_key")
        
        # Re-import job to apply the new environment variables
        import job
        self.job = job

    def test_call_llm_api_defaults_to_openrouter(self):
        """Test that call_llm_api defaults to openrouter when no provider is specified."""
        with patch.object(self.job, 'openrouter_client') as mock_openrouter:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
            mock_openrouter.chat.completions.create.return_value = mock_response
            
            result = self.job.call_llm_api("test-model", "system", "user")
            
            assert result == "Test response"
            mock_openrouter.chat.completions.create.assert_called_once()

    def test_call_llm_api_uses_aihubmix_client(self):
        """Test that call_llm_api uses aihubmix client when provider is aihubmix."""
        with patch.object(self.job, 'aihubmix_client') as mock_aihubmix:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="AIHubMix response"))]
            mock_aihubmix.chat.completions.create.return_value = mock_response
            
            result = self.job.call_llm_api("test-model", "system", "user", provider="aihubmix")
            
            assert result == "AIHubMix response"
            mock_aihubmix.chat.completions.create.assert_called_once()

    def test_call_llm_api_retries_on_failure(self):
        """Test that call_llm_api retries on failure."""
        with patch.object(self.job, 'openrouter_client') as mock_openrouter:
            # First two calls fail, third succeeds
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Success"))]
            mock_openrouter.chat.completions.create.side_effect = [
                Exception("Error 1"),
                Exception("Error 2"),
                mock_response
            ]
            
            result = self.job.call_llm_api("test-model", "system", "user")
            
            assert result == "Success"
            assert mock_openrouter.chat.completions.create.call_count == 3

    def test_call_llm_api_raises_after_max_retries(self):
        """Test that call_llm_api raises exception after max retries."""
        with patch.object(self.job, 'openrouter_client') as mock_openrouter:
            mock_openrouter.chat.completions.create.side_effect = Exception("Persistent error")
            
            with pytest.raises(Exception, match="Persistent error"):
                self.job.call_llm_api("test-model", "system", "user")
            
            assert mock_openrouter.chat.completions.create.call_count == 3

    def test_call_llm_api_raises_when_openrouter_client_is_none(self):
        """Test that call_llm_api raises error when OpenRouter client is None."""
        with patch.object(self.job, 'openrouter_client', None):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not set"):
                self.job.call_llm_api("test-model", "system", "user")

    def test_call_llm_api_raises_when_aihubmix_client_is_none(self):
        """Test that call_llm_api raises error when AIHubMix client is None."""
        with patch.object(self.job, 'aihubmix_client', None):
            with pytest.raises(ValueError, match="AIHUBMIX_API_KEY is not set"):
                self.job.call_llm_api("test-model", "system", "user", provider="aihubmix")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
