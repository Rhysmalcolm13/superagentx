import asyncio
import uuid
from typing import Literal

import yaml

from superagentx.agent.agent import Agent
from superagentx.agent.result import GoalResult
from superagentx.constants import SEQUENCE
from superagentx.exceptions import StopSuperAgentX
from superagentx.llm.types.base import logger
from superagentx.utils.helper import iter_to_aiter


class AgentXPipe:

    def __init__(
            self,
            *,
            pipe_id: str = uuid.uuid4().hex,
            name: str | None = None,
            description: str | None = None,
            agents: list[Agent | list[Agent]] | None = None,
            stop_if_goal_not_satisfied: bool = False
    ):
        """
        Initializes a new instance of the class with specified parameters.

        This constructor sets up an object that can manage a collection of agents,
        define a goal and role, and utilize a prompt for processing. Each instance
        can be uniquely identified by the `pipe_id`, which defaults to a newly
        generated UUID if not provided. This structure is particularly useful for
        organizing and executing workflows that involve multiple agents working
        toward a common goal.

        Args:
            pipe_id: A unique identifier for the agentxpipe. If not provided, a new UUID
                will be generated by default. Useful for tracking or referencing
                the agentxpipe in multi-agent environments.
            name: An optional name for the agentxpipe, providing a more friendly reference for display or
                logging purposes.
            description: An optional description that provides additional context or details about the agentxpipe's
                purpose and capabilities.
            agents: A list of Agent instances (or lists of Agent instances) that are part of this structure.
                These agents can perform tasks and contribute to achieving the defined goal.
            stop_if_goal_not_satisfied: A flag indicating whether to stop processing if the goal is not satisfied.
                When set to True, the agentxpipe operation will halt if the defined goal is not met,
                preventing any further actions. Defaults to False, allowing the process to continue regardless
                of goal satisfaction.
        """
        self.pipe_id = pipe_id
        self.name = name or f'{self.__str__()}-{self.pipe_id}'
        self.description = description
        self.agents: list[Agent | list[Agent]] = agents or []
        self.stop_if_goal_not_satisfied = stop_if_goal_not_satisfied

    def __str__(self):
        return "AgentXPipe"

    def __repr__(self):
        return f"<{self.__str__()}>"

    async def add(
            self,
            *agents: Agent,
            execute_type: Literal['SEQUENCE', 'PARALLEL'] = 'SEQUENCE'
    ) -> None:
        """
        Adds one or more Agent instances to the current context for processing.

        This method allows the user to include multiple agents that will be used
        for execution based on the specified execution type. The `execute_type`
        parameter determines how the engines will be run: either in a sequence,
        where each agent runs one after the other, or in parallel, where all
        specified agents run concurrently.

        Args:
            agents: One or more Agent instances to be added to the context.
                This allows for flexibility in processing and task execution based on different capabilities
                or configurations.
            execute_type: The method of execution for the added engines.
                - 'SEQUENCE': Agents are executed one after another,
                  waiting for each to complete before starting the next.
                - 'PARALLEL': All agents are executed concurrently, allowing for
                  simultaneous processing.
                Default is 'SEQUENCE'.

        Returns:
            None
        """
        if execute_type == SEQUENCE:
            self.agents += agents
        else:
            self.agents.append(list(agents))

    @staticmethod
    async def _pre_result(
            results: list[GoalResult] | None = None
    ) -> list[str]:
        if not results:
            return []
        return [
            (f'Reason: {result.reason}\n'
             f'Result: \n{yaml.dump(result.result)}\n'
             f'Is Goal Satisfied: {result.is_goal_satisfied}\n\n')
            async for result in iter_to_aiter(results)
        ]

    async def _flow(
            self,
            query_instruction: str
    ):
        trigger_break = False
        results = []
        async for _agents in iter_to_aiter(self.agents):
            pre_result = await self._pre_result(results=results)
            try:
                if isinstance(_agents, list):
                    _res = await asyncio.gather(
                        *[
                            _agent.execute(
                                query_instruction=query_instruction,
                                pre_result=pre_result,
                                stop_if_goal_not_satisfied=self.stop_if_goal_not_satisfied
                            )
                            async for _agent in iter_to_aiter(_agents)
                        ]
                    )
                else:
                    _res = await _agents.execute(
                        query_instruction=query_instruction,
                        pre_result=pre_result,
                        stop_if_goal_not_satisfied=self.stop_if_goal_not_satisfied
                    )
            except StopSuperAgentX as ex:
                trigger_break = True
                logger.warning(ex)
                _res = ex.goal_result

            results.append(_res)
            if trigger_break:
                break
        return results

    async def flow(
            self,
            query_instruction: str
    ) -> list[GoalResult]:
        """
        Processes the specified query instruction and executes a flow of operations.

        This method interprets the `query_instruction` and coordinates a series of
        actions aimed at achieving the associated goals. It can involve multiple agents
        and may utilize previously defined workflows to effectively generate results.
        The method returns a list of GoalResult instances that indicate the outcomes of
        the executed operations.

        Args:
            query_instruction: A string representing the instruction or query that defines the goal to be achieved.
                This should be a clear and actionable statement that the method can execute.

        Returns:
            list[GoalResult]
                A list of GoalResult instances representing the outcomes of the operations executed in response to
                the query instruction. Each GoalResult provides details about the success or failure of the
                corresponding operation and may include additional context or data.
        """
        logger.info(f"Pipe {self.name} starting...")
        return await self._flow(
            query_instruction=query_instruction
        )
