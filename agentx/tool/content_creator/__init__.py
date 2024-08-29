from enum import Enum
from typing import Any

from langchain_core.language_models.chat_models import BaseLanguageModel
from langchain_openai.chat_models import ChatOpenAI
from pydantic import BaseModel

from agentx.exceptions import UnSupportedType
from agentx.tool.base import BaseHandler


class ContentCreatorType(Enum):
    TEXT = "TEXT"
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"


class ContentCreatorHandler(BaseHandler):

    def __init__(
            self,
            prompt: str,
            llm: BaseLanguageModel
    ):
        self.prompt = prompt
        self.llm = llm

    def handle(
            self,
            action: str | Enum,
            *args,
            **kwargs
    ) -> Any:
        match action:
            case ContentCreatorType.TEXT:
                result = self.text_creation()
            case ContentCreatorType.IMAGE:
                raise NotImplementedError(f"{action} future will be implement")
            case ContentCreatorType.VIDEO:
                raise NotImplementedError(f"{action} future will be implement")
            case _:
                raise UnSupportedType(f"{action} is not supported")
        return result

    def text_creation(self):
        messages = self.prompt
        if isinstance(self.llm, ChatOpenAI):
            messages = [
                (
                    "human",
                    self.prompt
                )
            ]
        chain = self.llm.invoke(messages)
        return chain

    def video_creation(self):
        raise NotImplementedError

    def image_creation(self):
        raise NotImplementedError
