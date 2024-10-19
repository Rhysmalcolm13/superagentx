import asyncio
import json
import logging
import uuid
from json import JSONDecodeError
from typing import Literal, Any

from superagentx.agent.engine import Engine
from superagentx.agent.result import GoalResult
from superagentx.constants import SEQUENCE
from superagentx.exceptions import StopSuperAgentX
from superagentx.llm import LLMClient, ChatCompletionParams
from superagentx.prompt import PromptTemplate
from superagentx.utils.helper import iter_to_aiter

logger = logging.getLogger(__name__)

_GOAL_PROMPT_TEMPLATE = """Review the given output context and make sure

the following goal is achieved.

Goal: {goal}

Query_Instruction: {query_instruction}

Output_Context : {output_context}

Feedback: {feedback}

Output_Format: {output_format}

Follow the instructions step-by-step carefully and act upon.

Review the Output_Context based on the given Goal with Query_Instruction and set the result in the below mentioned result.

Answer should be based on the given output context. Do not try answer by your own.

Make sure generate the result based on the given output format if provided. 

{{
    reason: Set the reason for result,
    result: Set this based on given output format if output format given. Otherwise set the result as it is.,
    is_goal_satisfied: 'True' if result satisfied based on the given goal. Otherwise set as 'False'. Set only 'True' or 'False' boolean.
}}

Always generate the JSON output.
"""


class Agent:

    def __init__(
            self,
            *,
            goal: str,
            role: str,
            llm: LLMClient,
            prompt_template: PromptTemplate,
            agent_id: str | None = uuid.uuid4().hex,
            name: str | None = None,
            description: str | None = None,
            engines: list[Engine | list[Engine]] | None = None,
            output_format: str | None = None,
            max_retry: int = 5
    ):
        """
        Initializes a new instance of the Agent class.

        This constructor sets up an agent with specific goals and roles, allowing
        it to interact with a large language model (LLM) and utilize a defined
        prompt template. The agent can be configured with various parameters to
        tailor its behavior to specific tasks and workflows.

        Args:
            goal: The primary objective or goal that the agent is designed to achieve.
            role: The role or function that the agent will assume in its operations.
            llm: Interface for communicating with the large language model (LLM).
            prompt_template: Defines the structure and format of prompts sent to the LLM using `PromptTemplate`.
            agent_id: A unique identifier for the agent. If not provided, a new UUID
                will be generated by default. Useful for tracking or referencing
                the agent in multi-agent environments.
            name: An optional name for the agent, providing a more friendly reference for display or logging purposes.
            description: An optional description that provides additional context or details about the agent's
                purpose and capabilities.
            engines: A list of engines (or lists of engines) that the agent can utilize.
                This allows for flexibility in processing and task execution based on different capabilities
                or configurations.
            output_format: Specifies the desired format for the agent's output. This can dictate how results are
                structured and presented.
            max_retry: The maximum number of retry attempts for operations that may fail.
                Default is set to 5. This is particularly useful in scenarios where transient errors may occur,
                ensuring robust execution.
        """
        self.role = role
        self.goal = goal
        self.llm = llm
        self.prompt_template = prompt_template
        self.agent_id = agent_id
        self.name = name or f'{self.__str__()}-{self.agent_id}'
        self.description = description
        self.engines: list[Engine | list[Engine]] = engines or []
        self.output_format = output_format
        self.max_retry = max_retry

    def __str__(self):
        return "Agent"

    def __repr__(self):
        return f"<{self.__str__()}>"

    async def add(
            self,
            *engines: Engine,
            execute_type: Literal['SEQUENCE', 'PARALLEL'] = 'SEQUENCE'
    ) -> None:
        """
        Adds one or more Engine instances to the current context for processing.

        This method allows the user to include multiple engines that will be used
        for execution based on the specified execution type. The `execute_type`
        parameter determines how the engines will be run: either in a sequence,
        where each engine runs one after the other, or in parallel, where all
        specified engines run concurrently.

        Args:
            engines: One or more Engine instances to be added to the context.
                This allows for flexibility in processing and task execution based on different capabilities
                or configurations.
            execute_type: The method of execution for the added engines.
                - 'SEQUENCE': Engines are executed one after another,
                  waiting for each to complete before starting the next.
                - 'PARALLEL': All engines are executed concurrently, allowing for
                  simultaneous processing.
                Default is 'SEQUENCE'.

        Returns:
            None
        """
        if execute_type == SEQUENCE:
            self.engines += engines
        else:
            self.engines.append(list(engines))

    async def _verify_goal(
            self,
            *,
            query_instruction: str,
            results: list[Any]
    ) -> GoalResult:
        prompt_message = await self.prompt_template.get_messages(
            input_prompt=_GOAL_PROMPT_TEMPLATE,
            goal=self.goal,
            query_instruction=query_instruction,
            output_context=results,
            feedback="",
            output_format=self.output_format or ""
        )
        messages = prompt_message
        chat_completion_params = ChatCompletionParams(
            messages=messages
        )
        messages = await self.llm.achat_completion(
            chat_completion_params=chat_completion_params
        )
        logger.debug(f"Goal pre result => {messages}")
        if messages and messages.choices:
            for choice in messages.choices:
                if choice and choice.message:
                    _res = choice.message.content or ''
                    _res = _res.replace('```json', '').replace('```', '')
                    try:
                        __res = json.loads(_res)
                        return GoalResult(
                            name=self.name,
                            agent_id=self.agent_id,
                            **__res
                        )
                    except JSONDecodeError as ex:
                        _msg = f'Cannot verify goal!\n{ex}'
                        logger.warning(_msg)
                        return GoalResult(
                            name=self.name,
                            agent_id=self.agent_id,
                            content=_res,
                            error=_msg
                        )
        else:
            return GoalResult(
                name=self.name,
                agent_id=self.agent_id,
                error='No results found!',
                is_goal_satisfied=False
            )

    async def _execute(
            self,
            query_instruction: str,
            pre_result: str | None = None,
            old_memory: str | None = None
    ) -> GoalResult:
        results = []
        instruction = query_instruction
        if old_memory:
            instruction = f"Context:\n{old_memory}\nQuestion: {query_instruction}"
        async for _engines in iter_to_aiter(self.engines):
            if isinstance(_engines, list):
                _res = await asyncio.gather(
                    *[
                        _engine.start(
                            input_prompt=instruction,
                            pre_result=pre_result
                        )
                        async for _engine in iter_to_aiter(_engines)
                    ]
                )
            else:
                _res = await _engines.start(
                    input_prompt=instruction,
                    pre_result=pre_result
                )
            results.append(_res)
        logger.debug(f"Engine results =>\n{results}")
        final_result = await self._verify_goal(
            results=results,
            query_instruction=query_instruction
        )
        logger.debug(f"Final Result =>\n, {final_result.model_dump()}")
        return final_result

    async def execute(
            self,
            *,
            query_instruction: str,
            pre_result: str | None = None,
            old_memory: str | None = None,
            stop_if_goal_not_satisfied: bool = False
    ) -> GoalResult | None:
        """
        Executes the specified query instruction to achieve a defined goal.

        This method processes the `query_instruction`, potentially utilizing any
        pre-existing results provided through the `pre_result` parameter. The execution
        is designed to perform the necessary operations to fulfill the goal associated
        with the instruction and return a structured result indicating the outcome.

        Args:
            query_instruction: A string representing the instruction or query that defines the goal to be achieved.
                This should be a clear and actionable statement that the method can execute.
            pre_result: An optional pre-computed result or state to be used during the execution.
                Defaults to `None` if not provided.
            old_memory: An optional previous context of the user's instruction
            stop_if_goal_not_satisfied: A flag indicating whether to stop processing if the goal is not satisfied.
                When set to True, the agent operation will halt if the defined goal is not met,
                preventing any further actions. Defaults to False, allowing the process to continue regardless
                of goal satisfaction.

        Returns:
            GoalResult | None
                An instance of the GoalResult class indicating the outcome of the execution. This result may include
                details about the success or failure of the operation, along with relevant data. If the
                execution cannot be completed or if an error occurs, the method may return `None`.
        """
        _goal_result = None
        for _retry in range(1, self.max_retry+1):
            logger.info(f"Agent `{self.name}` retry {_retry}")
            _goal_result = await self._execute(
                query_instruction=query_instruction,
                pre_result=pre_result,
                old_memory=old_memory
            )
            if _goal_result.is_goal_satisfied:
                return _goal_result
            elif _goal_result.is_goal_satisfied is False and stop_if_goal_not_satisfied:
                raise StopSuperAgentX(
                    message='Superagentx stopped forcefully since `stop` flag has been set!',
                    goal_result=_goal_result
                )

        logger.warning(f"Done agent `{self.name}` max retry {self.max_retry}!")
        return _goal_result
