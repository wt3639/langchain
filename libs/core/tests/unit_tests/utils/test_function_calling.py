# mypy: disable-error-code="annotation-unchecked"
from typing import Any, Callable, Dict, List, Literal, Optional, Type

import pytest
from pydantic import BaseModel as BaseModelV2Maybe  #  pydantic: ignore
from pydantic import Field as FieldV2Maybe  #  pydantic: ignore
from typing_extensions import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool, tool
from langchain_core.utils.function_calling import (
    convert_to_openai_function,
    tool_example_to_messages,
)


@pytest.fixture()
def pydantic() -> Type[BaseModel]:
    class dummy_function(BaseModel):
        """dummy function"""

        arg1: int = Field(..., description="foo")
        arg2: Literal["bar", "baz"] = Field(..., description="one of 'bar', 'baz'")

    return dummy_function


@pytest.fixture()
def annotated_function() -> Callable:
    def dummy_function(
        arg1: Annotated[int, "foo"],
        arg2: Annotated[Literal["bar", "baz"], "one of 'bar', 'baz'"],
    ) -> None:
        """dummy function"""
        pass

    return dummy_function


@pytest.fixture()
def function() -> Callable:
    def dummy_function(arg1: int, arg2: Literal["bar", "baz"]) -> None:
        """dummy function

        Args:
            arg1: foo
            arg2: one of 'bar', 'baz'
        """
        pass

    return dummy_function


@pytest.fixture()
def runnable() -> Runnable:
    class Args(TypedDict):
        arg1: Annotated[int, "foo"]
        arg2: Annotated[Literal["bar", "baz"], "one of 'bar', 'baz'"]

    def dummy_function(input_dict: Args) -> None:
        pass

    return RunnableLambda(dummy_function)


@pytest.fixture()
def dummy_tool() -> BaseTool:
    class Schema(BaseModel):
        arg1: int = Field(..., description="foo")
        arg2: Literal["bar", "baz"] = Field(..., description="one of 'bar', 'baz'")

    class DummyFunction(BaseTool):
        args_schema: Type[BaseModel] = Schema
        name: str = "dummy_function"
        description: str = "dummy function"

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            pass

    return DummyFunction()


@pytest.fixture()
def dummy_pydantic() -> Type[BaseModel]:
    class dummy_function(BaseModel):
        """dummy function"""

        arg1: int = Field(..., description="foo")
        arg2: Literal["bar", "baz"] = Field(..., description="one of 'bar', 'baz'")

    return dummy_function


@pytest.fixture()
def dummy_pydantic_v2() -> Type[BaseModelV2Maybe]:
    class dummy_function(BaseModelV2Maybe):
        """dummy function"""

        arg1: int = FieldV2Maybe(..., description="foo")
        arg2: Literal["bar", "baz"] = FieldV2Maybe(
            ..., description="one of 'bar', 'baz'"
        )

    return dummy_function


@pytest.fixture()
def json_schema() -> Dict:
    return {
        "title": "dummy_function",
        "description": "dummy function",
        "type": "object",
        "properties": {
            "arg1": {"description": "foo", "type": "integer"},
            "arg2": {
                "description": "one of 'bar', 'baz'",
                "enum": ["bar", "baz"],
                "type": "string",
            },
        },
        "required": ["arg1", "arg2"],
    }


class Dummy:
    def dummy_function(self, arg1: int, arg2: Literal["bar", "baz"]) -> None:
        """dummy function

        Args:
            arg1: foo
            arg2: one of 'bar', 'baz'
        """
        pass


class DummyWithClassMethod:
    @classmethod
    def dummy_function(cls, arg1: int, arg2: Literal["bar", "baz"]) -> None:
        """dummy function

        Args:
            arg1: foo
            arg2: one of 'bar', 'baz'
        """
        pass


def test_convert_to_openai_function(
    pydantic: Type[BaseModel],
    function: Callable,
    dummy_tool: BaseTool,
    json_schema: Dict,
    annotated_function: Callable,
    dummy_pydantic: Type[BaseModel],
    runnable: Runnable,
) -> None:
    expected = {
        "name": "dummy_function",
        "description": "dummy function",
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"description": "foo", "type": "integer"},
                "arg2": {
                    "description": "one of 'bar', 'baz'",
                    "enum": ["bar", "baz"],
                    "type": "string",
                },
            },
            "required": ["arg1", "arg2"],
        },
    }

    for fn in (
        pydantic,
        function,
        dummy_tool,
        json_schema,
        expected,
        Dummy.dummy_function,
        DummyWithClassMethod.dummy_function,
        annotated_function,
        dummy_pydantic,
    ):
        actual = convert_to_openai_function(fn)  # type: ignore
        assert actual == expected

    # Test runnables
    actual = convert_to_openai_function(runnable.as_tool(description="dummy function"))
    parameters = {
        "type": "object",
        "properties": {
            "arg1": {"type": "integer"},
            "arg2": {
                "enum": ["bar", "baz"],
                "type": "string",
            },
        },
        "required": ["arg1", "arg2"],
    }
    runnable_expected = expected.copy()
    runnable_expected["parameters"] = parameters
    assert actual == runnable_expected


def test_convert_to_openai_function_nested() -> None:
    class Nested(BaseModel):
        nested_arg1: int = Field(..., description="foo")
        nested_arg2: Literal["bar", "baz"] = Field(
            ..., description="one of 'bar', 'baz'"
        )

    class NestedV2(BaseModelV2Maybe):
        nested_v2_arg1: int = FieldV2Maybe(..., description="foo")
        nested_v2_arg2: Literal["bar", "baz"] = FieldV2Maybe(
            ..., description="one of 'bar', 'baz'"
        )

    def my_function(arg1: Nested, arg2: NestedV2) -> None:
        """dummy function"""
        pass

        expected = {
            "name": "my_function",
            "description": "dummy function",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {
                        "type": "object",
                        "properties": {
                            "nested_arg1": {"type": "integer", "description": "foo"},
                            "nested_arg2": {
                                "type": "string",
                                "enum": ["bar", "baz"],
                                "description": "one of 'bar', 'baz'",
                            },
                        },
                        "required": ["nested_arg1", "nested_arg2"],
                    },
                    "arg2": {
                        "type": "object",
                        "properties": {
                            "nested_v2_arg1": {"type": "integer", "description": "foo"},
                            "nested_v2_arg2": {
                                "type": "string",
                                "enum": ["bar", "baz"],
                                "description": "one of 'bar', 'baz'",
                            },
                        },
                        "required": ["nested_v2_arg1", "nested_v2_arg2"],
                    },
                },
                "required": ["arg1", "arg2"],
            },
        }

        actual = convert_to_openai_function(my_function)
        assert actual == expected


@pytest.mark.xfail(reason="Pydantic converts Optional[str] to str in .schema()")
def test_function_optional_param() -> None:
    @tool
    def func5(
        a: Optional[str],
        b: str,
        c: Optional[List[Optional[str]]],
    ) -> None:
        """A test function"""
        pass

    func = convert_to_openai_function(func5)
    req = func["parameters"]["required"]
    assert set(req) == {"b"}


def test_function_no_params() -> None:
    def nullary_function() -> None:
        """nullary function"""
        pass

    func = convert_to_openai_function(nullary_function)
    req = func["parameters"].get("required")
    assert not req


class FakeCall(BaseModel):
    data: str


def test_valid_example_conversion() -> None:
    expected_messages = [
        HumanMessage(content="This is a valid example"),
        AIMessage(content="", additional_kwargs={"tool_calls": []}),
    ]
    assert (
        tool_example_to_messages(input="This is a valid example", tool_calls=[])
        == expected_messages
    )


def test_multiple_tool_calls() -> None:
    messages = tool_example_to_messages(
        input="This is an example",
        tool_calls=[
            FakeCall(data="ToolCall1"),
            FakeCall(data="ToolCall2"),
            FakeCall(data="ToolCall3"),
        ],
    )
    assert len(messages) == 5
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert isinstance(messages[3], ToolMessage)
    assert isinstance(messages[4], ToolMessage)
    assert messages[1].additional_kwargs["tool_calls"] == [
        {
            "id": messages[2].tool_call_id,
            "type": "function",
            "function": {"name": "FakeCall", "arguments": '{"data": "ToolCall1"}'},
        },
        {
            "id": messages[3].tool_call_id,
            "type": "function",
            "function": {"name": "FakeCall", "arguments": '{"data": "ToolCall2"}'},
        },
        {
            "id": messages[4].tool_call_id,
            "type": "function",
            "function": {"name": "FakeCall", "arguments": '{"data": "ToolCall3"}'},
        },
    ]


def test_tool_outputs() -> None:
    messages = tool_example_to_messages(
        input="This is an example",
        tool_calls=[
            FakeCall(data="ToolCall1"),
        ],
        tool_outputs=["Output1"],
    )
    assert len(messages) == 3
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert messages[1].additional_kwargs["tool_calls"] == [
        {
            "id": messages[2].tool_call_id,
            "type": "function",
            "function": {"name": "FakeCall", "arguments": '{"data": "ToolCall1"}'},
        },
    ]
    assert messages[2].content == "Output1"
