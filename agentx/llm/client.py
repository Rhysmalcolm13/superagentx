from abc import ABCMeta, abstractmethod

from pydantic import typing


class Client(metaclass=ABCMeta):

    @abstractmethod
    def chat_completion(
            self,
            *args,
            **kwargs
    ):
        raise NotImplementedError

    @abstractmethod
    async def achat_completion(
            self,
            *args,
            **kwargs
    ):
        raise NotImplementedError

    @abstractmethod
    async def get_tool_json(
            self,
            func: typing.Callable
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def embed(
            self,
            text: str,
            **kwargs
    ):
        """
        Get the embedding for the given text using Client.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        raise NotImplementedError

    @abstractmethod
    async def aembed(
            self,
            text: str,
            **kwargs
    ):
        """
        Get the embedding for the given text using Client.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        raise NotImplementedError
