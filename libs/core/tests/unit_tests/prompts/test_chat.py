import base64
import tempfile
from pathlib import Path
from typing import Any, List, Union

import pytest
from syrupy import SnapshotAssertion

from langchain_core._api.deprecation import (
    LangChainPendingDeprecationWarning,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts.chat import (
    AIMessagePromptTemplate,
    BaseMessagePromptTemplate,
    ChatMessage,
    ChatMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    _convert_to_message,
)
from langchain_core.pydantic_v1 import ValidationError


@pytest.fixture
def messages() -> List[BaseMessagePromptTemplate]:
    """Create messages."""
    system_message_prompt = SystemMessagePromptTemplate(
        prompt=PromptTemplate(
            template="Here's some context: {context}",
            input_variables=["context"],
        )
    )
    human_message_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate(
            template="Hello {foo}, I'm {bar}. Thanks for the {context}",
            input_variables=["foo", "bar", "context"],
        )
    )
    ai_message_prompt = AIMessagePromptTemplate(
        prompt=PromptTemplate(
            template="I'm an AI. I'm {foo}. I'm {bar}.",
            input_variables=["foo", "bar"],
        )
    )
    chat_message_prompt = ChatMessagePromptTemplate(
        role="test",
        prompt=PromptTemplate(
            template="I'm a generic message. I'm {foo}. I'm {bar}.",
            input_variables=["foo", "bar"],
        ),
    )
    return [
        system_message_prompt,
        human_message_prompt,
        ai_message_prompt,
        chat_message_prompt,
    ]


@pytest.fixture
def chat_prompt_template(
    messages: List[BaseMessagePromptTemplate],
) -> ChatPromptTemplate:
    """Create a chat prompt template."""
    return ChatPromptTemplate(
        input_variables=["foo", "bar", "context"],
        messages=messages,  # type: ignore[arg-type]
    )


def test_create_chat_prompt_template_from_template() -> None:
    """Create a chat prompt template."""
    prompt = ChatPromptTemplate.from_template("hi {foo} {bar}")
    assert prompt.messages == [
        HumanMessagePromptTemplate.from_template("hi {foo} {bar}")
    ]


def test_create_chat_prompt_template_from_template_partial() -> None:
    """Create a chat prompt template with partials."""
    prompt = ChatPromptTemplate.from_template(
        "hi {foo} {bar}", partial_variables={"foo": "jim"}
    )
    expected_prompt = PromptTemplate(
        template="hi {foo} {bar}",
        input_variables=["bar"],
        partial_variables={"foo": "jim"},
    )
    assert len(prompt.messages) == 1
    output_prompt = prompt.messages[0]
    assert isinstance(output_prompt, HumanMessagePromptTemplate)
    assert output_prompt.prompt == expected_prompt


def test_create_system_message_prompt_template_from_template_partial() -> None:
    """Create a system message prompt template with partials."""

    graph_creator_content = """
    Your instructions are:
    {instructions}
    History:
    {history}
    """
    json_prompt_instructions: dict = {}
    graph_analyst_template = SystemMessagePromptTemplate.from_template(
        template=graph_creator_content,
        input_variables=["history"],
        partial_variables={"instructions": json_prompt_instructions},
    )
    assert graph_analyst_template.format(history="history") == SystemMessage(
        content="\n    Your instructions are:\n  "
        "  {}\n    History:\n    "
        "history\n    "
    )


def test_create_system_message_prompt_list_template() -> None:
    graph_creator_content1 = """
    This is the prompt for the first test:
    {variables}
    """
    graph_creator_content2 = """
    This is the prompt for the second test:
        {variables}
        """
    graph_analyst_template = SystemMessagePromptTemplate.from_template(
        template=[graph_creator_content1, graph_creator_content2],
        input_variables=["variables"],
    )
    assert graph_analyst_template.format(variables="foo") == SystemMessage(
        content=[
            {
                "type": "text",
                "text": "\n    This is the prompt for the first test:\n    foo\n    ",
            },
            {
                "type": "text",
                "text": "\n    This is the prompt for "
                "the second test:\n        foo\n        ",
            },
        ]
    )


def test_create_system_message_prompt_list_template_partial_variables_not_null() -> (
    None
):
    graph_creator_content1 = """
    This is the prompt for the first test:
    {variables}
    """
    graph_creator_content2 = """
    This is the prompt for the second test:
        {variables}
        """

    try:
        graph_analyst_template = SystemMessagePromptTemplate.from_template(
            template=[graph_creator_content1, graph_creator_content2],
            input_variables=["variables"],
            partial_variables={"variables": "foo"},
        )
        graph_analyst_template.format(variables="foo")
    except ValueError as e:
        assert str(e) == "Partial variables are not supported for list of templates."


def test_message_prompt_template_from_template_file() -> None:
    expected = ChatMessagePromptTemplate(
        prompt=PromptTemplate(
            template="Question: {question}\nAnswer:", input_variables=["question"]
        ),
        role="human",
    )
    actual = ChatMessagePromptTemplate.from_template_file(
        Path(__file__).parent.parent / "data" / "prompt_file.txt",
        ["question"],
        role="human",
    )
    assert expected == actual


async def test_chat_prompt_template(chat_prompt_template: ChatPromptTemplate) -> None:
    """Test chat prompt template."""
    prompt = chat_prompt_template.format_prompt(foo="foo", bar="bar", context="context")
    assert isinstance(prompt, ChatPromptValue)
    messages = prompt.to_messages()
    assert len(messages) == 4
    assert messages[0].content == "Here's some context: context"
    assert messages[1].content == "Hello foo, I'm bar. Thanks for the context"
    assert messages[2].content == "I'm an AI. I'm foo. I'm bar."
    assert messages[3].content == "I'm a generic message. I'm foo. I'm bar."

    async_prompt = await chat_prompt_template.aformat_prompt(
        foo="foo", bar="bar", context="context"
    )

    assert async_prompt.to_messages() == messages

    string = prompt.to_string()
    expected = (
        "System: Here's some context: context\n"
        "Human: Hello foo, I'm bar. Thanks for the context\n"
        "AI: I'm an AI. I'm foo. I'm bar.\n"
        "test: I'm a generic message. I'm foo. I'm bar."
    )
    assert string == expected

    string = chat_prompt_template.format(foo="foo", bar="bar", context="context")
    assert string == expected

    string = await chat_prompt_template.aformat(foo="foo", bar="bar", context="context")
    assert string == expected


def test_chat_prompt_template_from_messages(
    messages: List[BaseMessagePromptTemplate],
) -> None:
    """Test creating a chat prompt template from messages."""
    chat_prompt_template = ChatPromptTemplate.from_messages(messages)
    assert sorted(chat_prompt_template.input_variables) == sorted(
        ["context", "foo", "bar"]
    )
    assert len(chat_prompt_template.messages) == 4


async def test_chat_prompt_template_from_messages_using_role_strings() -> None:
    """Test creating a chat prompt template from role string messages."""
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful AI bot. Your name is {name}."),
            ("human", "Hello, how are you doing?"),
            ("ai", "I'm doing well, thanks!"),
            ("human", "{user_input}"),
        ]
    )

    expected = [
        SystemMessage(
            content="You are a helpful AI bot. Your name is Bob.", additional_kwargs={}
        ),
        HumanMessage(
            content="Hello, how are you doing?", additional_kwargs={}, example=False
        ),
        AIMessage(
            content="I'm doing well, thanks!", additional_kwargs={}, example=False
        ),
        HumanMessage(content="What is your name?", additional_kwargs={}, example=False),
    ]

    messages = template.format_messages(name="Bob", user_input="What is your name?")
    assert messages == expected

    messages = await template.aformat_messages(
        name="Bob", user_input="What is your name?"
    )
    assert messages == expected


def test_chat_prompt_template_from_messages_mustache() -> None:
    """Test creating a chat prompt template from role string messages."""
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful AI bot. Your name is {{name}}."),
            ("human", "Hello, how are you doing?"),
            ("ai", "I'm doing well, thanks!"),
            ("human", "{{user_input}}"),
        ],
        "mustache",
    )

    messages = template.format_messages(name="Bob", user_input="What is your name?")

    assert messages == [
        SystemMessage(
            content="You are a helpful AI bot. Your name is Bob.", additional_kwargs={}
        ),
        HumanMessage(
            content="Hello, how are you doing?", additional_kwargs={}, example=False
        ),
        AIMessage(
            content="I'm doing well, thanks!", additional_kwargs={}, example=False
        ),
        HumanMessage(content="What is your name?", additional_kwargs={}, example=False),
    ]


def test_chat_prompt_template_with_messages(
    messages: List[BaseMessagePromptTemplate],
) -> None:
    chat_prompt_template = ChatPromptTemplate.from_messages(
        messages + [HumanMessage(content="foo")]
    )
    assert sorted(chat_prompt_template.input_variables) == sorted(
        ["context", "foo", "bar"]
    )
    assert len(chat_prompt_template.messages) == 5
    prompt_value = chat_prompt_template.format_prompt(
        context="see", foo="this", bar="magic"
    )
    prompt_value_messages = prompt_value.to_messages()
    assert prompt_value_messages[-1] == HumanMessage(content="foo")


def test_chat_invalid_input_variables_extra() -> None:
    messages = [HumanMessage(content="foo")]
    with pytest.raises(ValueError):
        ChatPromptTemplate(
            messages=messages,  # type: ignore[arg-type]
            input_variables=["foo"],
            validate_template=True,  # type: ignore[arg-type]
        )
    assert (
        ChatPromptTemplate(messages=messages, input_variables=["foo"]).input_variables  # type: ignore[arg-type]
        == []
    )


def test_chat_invalid_input_variables_missing() -> None:
    messages = [HumanMessagePromptTemplate.from_template("{foo}")]
    with pytest.raises(ValueError):
        ChatPromptTemplate(
            messages=messages,  # type: ignore[arg-type]
            input_variables=[],
            validate_template=True,  # type: ignore[arg-type]
        )
    assert ChatPromptTemplate(
        messages=messages,  # type: ignore[arg-type]
        input_variables=[],  # type: ignore[arg-type]
    ).input_variables == ["foo"]


def test_infer_variables() -> None:
    messages = [HumanMessagePromptTemplate.from_template("{foo}")]
    prompt = ChatPromptTemplate(messages=messages)  # type: ignore[arg-type, call-arg]
    assert prompt.input_variables == ["foo"]


def test_chat_valid_with_partial_variables() -> None:
    messages = [
        HumanMessagePromptTemplate.from_template(
            "Do something with {question} using {context} giving it like {formatins}"
        )
    ]
    prompt = ChatPromptTemplate(
        messages=messages,  # type: ignore[arg-type]
        input_variables=["question", "context"],
        partial_variables={"formatins": "some structure"},
    )
    assert set(prompt.input_variables) == {"question", "context"}
    assert prompt.partial_variables == {"formatins": "some structure"}


def test_chat_valid_infer_variables() -> None:
    messages = [
        HumanMessagePromptTemplate.from_template(
            "Do something with {question} using {context} giving it like {formatins}"
        )
    ]
    prompt = ChatPromptTemplate(  # type: ignore[call-arg]
        messages=messages,  # type: ignore[arg-type]
        partial_variables={"formatins": "some structure"},  # type: ignore[arg-type]
    )
    assert set(prompt.input_variables) == {"question", "context"}
    assert prompt.partial_variables == {"formatins": "some structure"}


async def test_chat_from_role_strings() -> None:
    """Test instantiation of chat template from role strings."""
    with pytest.warns(LangChainPendingDeprecationWarning):
        template = ChatPromptTemplate.from_role_strings(
            [
                ("system", "You are a bot."),
                ("assistant", "hello!"),
                ("human", "{question}"),
                ("other", "{quack}"),
            ]
        )

    expected = [
        ChatMessage(content="You are a bot.", role="system"),
        ChatMessage(content="hello!", role="assistant"),
        ChatMessage(content="How are you?", role="human"),
        ChatMessage(content="duck", role="other"),
    ]

    messages = template.format_messages(question="How are you?", quack="duck")
    assert messages == expected

    messages = await template.aformat_messages(question="How are you?", quack="duck")
    assert messages == expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (
            ("human", "{question}"),
            HumanMessagePromptTemplate(
                prompt=PromptTemplate.from_template("{question}")
            ),
        ),
        (
            "{question}",
            HumanMessagePromptTemplate(
                prompt=PromptTemplate.from_template("{question}")
            ),
        ),
        (HumanMessage(content="question"), HumanMessage(content="question")),
        (
            HumanMessagePromptTemplate(
                prompt=PromptTemplate.from_template("{question}")
            ),
            HumanMessagePromptTemplate(
                prompt=PromptTemplate.from_template("{question}")
            ),
        ),
    ],
)
def test_convert_to_message(
    args: Any, expected: Union[BaseMessage, BaseMessagePromptTemplate]
) -> None:
    """Test convert to message."""
    assert _convert_to_message(args) == expected


def test_chat_prompt_template_indexing() -> None:
    message1 = SystemMessage(content="foo")
    message2 = HumanMessage(content="bar")
    message3 = HumanMessage(content="baz")
    template = ChatPromptTemplate.from_messages([message1, message2, message3])
    assert template[0] == message1
    assert template[1] == message2

    # Slice starting from index 1
    slice_template = template[1:]
    assert slice_template[0] == message2
    assert len(slice_template) == 2


def test_chat_prompt_template_append_and_extend() -> None:
    """Test append and extend methods of ChatPromptTemplate."""
    message1 = SystemMessage(content="foo")
    message2 = HumanMessage(content="bar")
    message3 = HumanMessage(content="baz")
    template = ChatPromptTemplate.from_messages([message1])
    template.append(message2)
    template.append(message3)
    assert len(template) == 3
    template.extend([message2, message3])
    assert len(template) == 5
    assert template.messages == [
        message1,
        message2,
        message3,
        message2,
        message3,
    ]
    template.append(("system", "hello!"))
    assert template[-1] == SystemMessagePromptTemplate.from_template("hello!")


def test_convert_to_message_is_strict() -> None:
    """Verify that _convert_to_message is strict."""
    with pytest.raises(ValueError):
        # meow does not correspond to a valid message type.
        # this test is here to ensure that functionality to interpret `meow`
        # as a role is NOT added.
        _convert_to_message(("meow", "question"))


def test_chat_message_partial() -> None:
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an AI assistant named {name}."),
            ("human", "Hi I'm {user}"),
            ("ai", "Hi there, {user}, I'm {name}."),
            ("human", "{input}"),
        ]
    )
    template2 = template.partial(user="Lucy", name="R2D2")
    with pytest.raises(KeyError):
        template.format_messages(input="hello")

    res = template2.format_messages(input="hello")
    expected = [
        SystemMessage(content="You are an AI assistant named R2D2."),
        HumanMessage(content="Hi I'm Lucy"),
        AIMessage(content="Hi there, Lucy, I'm R2D2."),
        HumanMessage(content="hello"),
    ]
    assert res == expected
    assert template2.format(input="hello") == get_buffer_string(expected)


async def test_chat_tmpl_from_messages_multipart_text() -> None:
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an AI assistant named {name}."),
            (
                "human",
                [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "text", "text": "Oh nvm"},
                ],
            ),
        ]
    )
    expected = [
        SystemMessage(content="You are an AI assistant named R2D2."),
        HumanMessage(
            content=[
                {"type": "text", "text": "What's in this image?"},
                {"type": "text", "text": "Oh nvm"},
            ]
        ),
    ]
    messages = template.format_messages(name="R2D2")
    assert messages == expected

    messages = await template.aformat_messages(name="R2D2")
    assert messages == expected


async def test_chat_tmpl_from_messages_multipart_text_with_template() -> None:
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an AI assistant named {name}."),
            (
                "human",
                [
                    {"type": "text", "text": "What's in this {object_name}?"},
                    {"type": "text", "text": "Oh nvm"},
                ],
            ),
        ]
    )
    expected = [
        SystemMessage(content="You are an AI assistant named R2D2."),
        HumanMessage(
            content=[
                {"type": "text", "text": "What's in this image?"},
                {"type": "text", "text": "Oh nvm"},
            ]
        ),
    ]
    messages = template.format_messages(name="R2D2", object_name="image")
    assert messages == expected

    messages = await template.aformat_messages(name="R2D2", object_name="image")
    assert messages == expected


async def test_chat_tmpl_from_messages_multipart_image() -> None:
    """Test multipart image URL formatting."""
    base64_image = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAA"
    other_base64_image = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAA"
    template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an AI assistant named {name}."),
            (
                "human",
                [
                    {"type": "text", "text": "What's in this image?"},
                    {
                        "type": "image_url",
                        "image_url": "data:image/jpeg;base64,{my_image}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,{my_image}"},
                    },
                    {"type": "image_url", "image_url": "{my_other_image}"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "{my_other_image}", "detail": "medium"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://www.langchain.com/image.png"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,foobar"},
                    },
                ],
            ),
        ]
    )
    expected = [
        SystemMessage(content="You are an AI assistant named R2D2."),
        HumanMessage(
            content=[
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{other_base64_image}"
                    },
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"{other_base64_image}"},
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"{other_base64_image}",
                        "detail": "medium",
                    },
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "https://www.langchain.com/image.png"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,foobar"},
                },
            ]
        ),
    ]
    messages = template.format_messages(
        name="R2D2", my_image=base64_image, my_other_image=other_base64_image
    )
    assert messages == expected

    messages = await template.aformat_messages(
        name="R2D2", my_image=base64_image, my_other_image=other_base64_image
    )
    assert messages == expected


async def test_chat_tmpl_from_messages_multipart_formatting_with_path() -> None:
    """Verify that we can pass `path` for an image as a variable."""
    in_mem = "base64mem"
    in_file_data = "base64file01"

    with tempfile.NamedTemporaryFile(delete=True, suffix=".jpg") as temp_file:
        temp_file.write(base64.b64decode(in_file_data))
        temp_file.flush()

        template = ChatPromptTemplate.from_messages(
            [
                ("system", "You are an AI assistant named {name}."),
                (
                    "human",
                    [
                        {"type": "text", "text": "What's in this image?"},
                        {
                            "type": "image_url",
                            "image_url": "data:image/jpeg;base64,{in_mem}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"path": "{file_path}"},
                        },
                    ],
                ),
            ]
        )
        expected = [
            SystemMessage(content="You are an AI assistant named R2D2."),
            HumanMessage(
                content=[
                    {"type": "text", "text": "What's in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{in_mem}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{in_file_data}"},
                    },
                ]
            ),
        ]
        messages = template.format_messages(
            name="R2D2",
            in_mem=in_mem,
            file_path=temp_file.name,
        )
        assert messages == expected

        messages = await template.aformat_messages(
            name="R2D2",
            in_mem=in_mem,
            file_path=temp_file.name,
        )
        assert messages == expected


def test_messages_placeholder() -> None:
    prompt = MessagesPlaceholder("history")
    with pytest.raises(KeyError):
        prompt.format_messages()
    prompt = MessagesPlaceholder("history", optional=True)
    assert prompt.format_messages() == []
    assert prompt.format_messages(
        history=[("system", "You are an AI assistant."), "Hello!"]
    ) == [
        SystemMessage(content="You are an AI assistant."),
        HumanMessage(content="Hello!"),
    ]


def test_messages_placeholder_with_max() -> None:
    history = [
        AIMessage(content="1"),
        AIMessage(content="2"),
        AIMessage(content="3"),
    ]
    prompt = MessagesPlaceholder("history")
    assert prompt.format_messages(history=history) == history
    prompt = MessagesPlaceholder("history", n_messages=2)
    assert prompt.format_messages(history=history) == [
        AIMessage(content="2"),
        AIMessage(content="3"),
    ]


def test_chat_prompt_message_placeholder_partial() -> None:
    prompt = ChatPromptTemplate.from_messages([MessagesPlaceholder("history")])
    prompt = prompt.partial(history=[("system", "foo")])
    assert prompt.format_messages() == [SystemMessage(content="foo")]
    assert prompt.format_messages(history=[("system", "bar")]) == [
        SystemMessage(content="bar")
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder("history", optional=True),
        ]
    )
    assert prompt.format_messages() == []
    prompt = prompt.partial(history=[("system", "foo")])
    assert prompt.format_messages() == [SystemMessage(content="foo")]


def test_chat_prompt_message_placeholder_tuple() -> None:
    prompt = ChatPromptTemplate.from_messages([("placeholder", "{convo}")])
    assert prompt.format_messages(convo=[("user", "foo")]) == [
        HumanMessage(content="foo")
    ]

    assert prompt.format_messages() == []

    # Is optional = True
    optional_prompt = ChatPromptTemplate.from_messages(
        [("placeholder", ["{convo}", False])]
    )
    assert optional_prompt.format_messages(convo=[("user", "foo")]) == [
        HumanMessage(content="foo")
    ]
    with pytest.raises(KeyError):
        assert optional_prompt.format_messages() == []


async def test_messages_prompt_accepts_list() -> None:
    prompt = ChatPromptTemplate.from_messages([MessagesPlaceholder("history")])
    value = prompt.invoke([("user", "Hi there")])  # type: ignore
    assert value.to_messages() == [HumanMessage(content="Hi there")]

    value = await prompt.ainvoke([("user", "Hi there")])  # type: ignore
    assert value.to_messages() == [HumanMessage(content="Hi there")]

    # Assert still raises a nice error
    prompt = ChatPromptTemplate.from_messages(
        [("system", "You are a {foo}"), MessagesPlaceholder("history")]
    )
    with pytest.raises(TypeError):
        prompt.invoke([("user", "Hi there")])  # type: ignore

    with pytest.raises(TypeError):
        await prompt.ainvoke([("user", "Hi there")])  # type: ignore


def test_chat_input_schema(snapshot: SnapshotAssertion) -> None:
    prompt_all_required = ChatPromptTemplate.from_messages(
        messages=[MessagesPlaceholder("history", optional=False), ("user", "${input}")]
    )
    prompt_all_required.input_variables == {"input"}
    prompt_all_required.optional_variables == {"history"}
    with pytest.raises(ValidationError):
        prompt_all_required.input_schema(input="")
    assert prompt_all_required.input_schema.schema() == snapshot(name="required")
    prompt_optional = ChatPromptTemplate.from_messages(
        messages=[MessagesPlaceholder("history", optional=True), ("user", "${input}")]
    )
    prompt_optional.input_variables == {"history", "input"}
    prompt_optional.input_schema(input="")  # won't raise error
    prompt_optional.input_schema.schema() == snapshot(name="partial")
