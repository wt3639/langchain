"""Test chat model integration."""

import os

import pytest
from anthropic.types import ContentBlock, Message, Usage
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from langchain_anthropic import ChatAnthropic, ChatAnthropicMessages

os.environ["ANTHROPIC_API_KEY"] = "foo"


def test_initialization() -> None:
    """Test chat model initialization."""
    ChatAnthropicMessages(model_name="claude-instant-1.2", anthropic_api_key="xyz")
    ChatAnthropicMessages(model="claude-instant-1.2", anthropic_api_key="xyz")


@pytest.mark.requires("anthropic")
def test_anthropic_model_name_param() -> None:
    llm = ChatAnthropic(model_name="foo")
    assert llm.model == "foo"


@pytest.mark.requires("anthropic")
def test_anthropic_model_param() -> None:
    llm = ChatAnthropic(model="foo")
    assert llm.model == "foo"


@pytest.mark.requires("anthropic")
def test_anthropic_model_kwargs() -> None:
    llm = ChatAnthropic(model_name="foo", model_kwargs={"foo": "bar"})
    assert llm.model_kwargs == {"foo": "bar"}


@pytest.mark.requires("anthropic")
def test_anthropic_invalid_model_kwargs() -> None:
    with pytest.raises(ValueError):
        ChatAnthropic(model="foo", model_kwargs={"max_tokens_to_sample": 5})


@pytest.mark.requires("anthropic")
def test_anthropic_incorrect_field() -> None:
    with pytest.warns(match="not default parameter"):
        llm = ChatAnthropic(model="foo", foo="bar")
    assert llm.model_kwargs == {"foo": "bar"}


@pytest.mark.requires("anthropic")
def test_anthropic_initialization() -> None:
    """Test anthropic initialization."""
    # Verify that chat anthropic can be initialized using a secret key provided
    # as a parameter rather than an environment variable.
    ChatAnthropic(model="test", anthropic_api_key="test")


def test__format_output() -> None:
    anthropic_msg = Message(
        id="foo",
        content=[ContentBlock(type="text", text="bar")],
        model="baz",
        role="assistant",
        stop_reason=None,
        stop_sequence=None,
        usage=Usage(input_tokens=2, output_tokens=1),
        type="message",
    )
    expected = ChatResult(
        generations=[
            ChatGeneration(message=AIMessage("bar")),
        ],
        llm_output={
            "id": "foo",
            "model": "baz",
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 2, "output_tokens": 1},
        },
    )
    llm = ChatAnthropic(model="test", anthropic_api_key="test")
    actual = llm._format_output(anthropic_msg)
    assert expected == actual
