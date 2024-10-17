import inspect
import logging
import typing

from superagentx.exceptions import ToolError
from superagentx.handler.base import BaseHandler
from superagentx.handler.exceptions import InvalidHandler
from superagentx.llm import LLMClient, ChatCompletionParams
from superagentx.prompt import PromptTemplate
from superagentx.utils.helper import iter_to_aiter, sync_to_async
from superagentx.utils.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class Engine:

    def __init__(
            self,
            *,
            handler: BaseHandler,
            llm: LLMClient,
            prompt_template: PromptTemplate,
            tools: list[dict] | list[str] | None = None,
            output_parser: BaseParser | None = None
    ):
        """
        Initializes a new instance of the Engine class.

        This wraps BaseHandler implementation(s) and helps to trigger the handlers using llm and given prompt

        Args:
            handler: Implementation of `BaseHandler`, it method(s) will be executed based on the given prompts
            llm: Interface for communicating with the large language model (LLM).
            prompt_template: Defines the structure and format of prompts sent to the LLM using `PromptTemplate`.
            tools: List of handler method names (as dictionaries or strings) available for use during interactions.
                Defaults to `None`. If nothing provide `Engine` will get it dynamically using `dir(handler)`.
            output_parser: An optional parser to format and process the handler tools output. Defaults to `None`.
        """
        self.handler = handler
        self.llm = llm
        self.prompt_template = prompt_template
        self.tools = tools
        self.output_parser = output_parser

    async def __funcs_props(
            self,
            funcs: list[str]
    ) -> list[dict]:
        _funcs_props: list[dict] = []
        async for _func_name in iter_to_aiter(funcs):
            _func_name = _func_name.split('.')[-1]
            _func = getattr(self.handler, _func_name)
            logger.debug(f"Func Name => {_func_name}, Func => {_func}")
            if inspect.ismethod(_func) or inspect.isfunction(_func):
                logger.debug(f"{_func_name} is function!")
                _funcs_props.append(await self.llm.get_tool_json(func=_func))
        return _funcs_props

    async def _construct_tools(self) -> list[dict]:
        funcs = dir(self.handler)
        logger.debug(f"Handler Funcs => {funcs}")
        if not funcs:
            raise InvalidHandler(str(self.handler))

        _tools: list[dict] = []
        if self.tools:
            _tools = await self.__funcs_props(funcs=self.tools)
        if not _tools:
            _tools = await self.__funcs_props(funcs=funcs)
        return _tools

    async def start(
            self,
            input_prompt: str,
            pre_result: str | None = None,
            **kwargs
    ) -> list[typing.Any]:
        """
        Initiates a process using the given input prompt and optional pre-processing result.

        Args:
            input_prompt: The input string to initiate the process. This could be a query, command, or instruction
                 based on the context.
            pre_result: An optional pre-computed result or state to be used during the execution.
                Defaults to `None` if not provided.
            kwargs: Additional keyword arguments to update the `input_prompt` dynamically.

        Returns:
            list[typing.Any]
                A list of results generated during the process. The content and
                structure of the list depend on the implementation details.
        """
        if pre_result:
            input_prompt = f'{input_prompt}\n\n{pre_result}'

        if not kwargs:
            kwargs = {}
        prompt_messages = await self.prompt_template.get_messages(
            input_prompt=input_prompt,
            **kwargs
        )
        logger.debug(f"Prompt message => {prompt_messages}")
        tools = await self._construct_tools()
        logger.debug(f"Handler Tools => {tools}")
        chat_completion_params = ChatCompletionParams(
            messages=prompt_messages,
            tools=tools
        )
        logger.debug(f"Chat completion params => {chat_completion_params.model_dump_json(exclude_none=True)}")
        messages = await self.llm.afunc_chat_completion(
            chat_completion_params=chat_completion_params
        )
        logger.debug(f"Func chat completion => {messages}")
        if not messages:
            raise ToolError("Tool not found for the inputs!")

        results = []
        async for message in iter_to_aiter(messages):
            if message.tool_calls:
                async for tool in iter_to_aiter(message.tool_calls):
                    if tool.tool_type == 'function':
                        func = getattr(self.handler, tool.name)
                        if func and (inspect.ismethod(func) or inspect.isfunction(func)):
                            _kwargs = tool.arguments or {}
                            if inspect.iscoroutinefunction(func):
                                res = await func(**_kwargs)
                            else:
                                res = await sync_to_async(func, **_kwargs)

                            if res:
                                if not self.output_parser:
                                    results.append(res)
                                else:
                                    results.append(await self.output_parser.parse(res))
            else:
                results.append(message.content)
        return results
