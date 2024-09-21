import os
from agentx.handler.content_creator import ContentCreatorHandler
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "<OPENAI_API_KEY>"
content_creator_handler = ContentCreatorHandler(
    prompt="Create the digital marketing content",
    llm=ChatOpenAI(model="gpt-4o")
)


def test_handle_1():
    result = content_creator_handler.handle(action="TEXT")
    assert "digital marketing" in result
