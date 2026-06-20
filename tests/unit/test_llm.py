from unittest.mock import MagicMock

from smith.llm.deepseek_provider import DeepSeekProvider
from smith.llm.factory import get_llm_provider
from smith.llm.openai_provider import OpenAIProvider


def _mock_completion(content: str = "hello") -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_openai_provider_generate(config_with_openai):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("analysis result")
    provider = OpenAIProvider(config_with_openai, client=client)
    result = provider.generate("test prompt", system="be helpful")
    assert result == "analysis result"
    assert provider.name == "OpenAI"
    client.chat.completions.create.assert_called_once()


def test_deepseek_provider_generate(config_with_deepseek):
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("deep result")
    provider = DeepSeekProvider(config_with_deepseek, client=client)
    result = provider.generate("test prompt")
    assert result == "deep result"
    assert provider.name == "DeepSeek"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "deepseek-v4-flash"


def test_deepseek_provider_normalizes_legacy_model(config_with_deepseek):
    config_with_deepseek.deepseek_model = "deepseek-chat"
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_completion("ok")
    provider = DeepSeekProvider(config_with_deepseek, client=client)
    provider.generate("test")
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "deepseek-v4-flash"


def test_factory_openai(config_with_openai):
    provider = get_llm_provider(config_with_openai)
    assert isinstance(provider, OpenAIProvider)


def test_factory_deepseek(config_with_deepseek):
    provider = get_llm_provider(config_with_deepseek)
    assert isinstance(provider, DeepSeekProvider)
