import logging
from enum import Enum
from typing import Any

from jira import JIRA

from agentx.handler.base import BaseHandler
from agentx.handler.exceptions import InvalidAction
from agentx.handler.jira.exceptions import SprintException, AuthException, ProjectException, TaskException
from agentx.utils.helper import sync_to_async, iter_to_aiter

logger = logging.getLogger(__name__)


class JiraActions(str, Enum):
    PROJECT = 'project'
    ACTIVE_SPRINT = 'active_sprint'
    CREATE_SPRINT = 'create_sprint'
    GET_ISSUE = 'get_issue'
    ADD_ISSUE_TO_SPRINT = 'add_issue_to_sprint'
    MOVE_TO_BACKLOG = 'move_to_backlog'
    ADD_COMMENT = 'add_comment'
    CREATE_ISSUE = 'create_issue'
    ASSIGN_ISSUE = 'assign_issue'


class JiraHandler(BaseHandler):
    """
        A handler class for managing interactions with the Jira API.
        This class extends BaseHandler and provides methods for performing various Jira operations,
        such as creating, updating, retrieving, and managing issues and projects within a Jira environment.
    """

    def __init__(
            self,
            *,
            email: str,
            token: str,
            organization: str
    ):
        self.email = email
        self.token = token
        self.organization = organization
        self._connection: JIRA = self._connect()

    def _connect(self) -> JIRA:
        try:
            jira = JIRA(
                server=f'https://{self.organization}.atlassian.net',
                basic_auth=(self.email, self.token)
            )
            logger.debug("Authenticate Success")
            return jira
        except Exception as ex:
            message = f'JIRA Handler Authentication Problem {ex}'
            logger.error(message, exc_info=ex)
            raise AuthException(message)

    async def handle(
            self,
            *,
            action: str | Enum,
            **kwargs
    ) -> Any:

        """
        Asynchronously processes the specified action, which can be a string or an Enum, along with any additional
        keyword arguments. This method executes the corresponding logic based on the provided action and parameters.

        parameters:
            action (str | Enum): The action to be performed. This can either be a string or an Enum value representing
                                the action.
            **kwargs: Additional keyword arguments that may be passed to customize the behavior of the handler.

        Returns:
            Any: The result of handling the action. The return type may vary depending on the specific action handled.
        """

        if isinstance(action, str):
            action = action.lower()
        match action:
            case JiraActions.PROJECT:
                return await self.get_list_projects()
            case JiraActions.ACTIVE_SPRINT:
                return await self.get_active_sprint(**kwargs)
            case JiraActions.CREATE_SPRINT:
                return await self.create_sprint(**kwargs)
            case JiraActions.GET_ISSUE:
                return await self.get_issue(**kwargs)
            case JiraActions.ADD_ISSUE_TO_SPRINT:
                return await self.add_issue_to_sprint(**kwargs)
            case JiraActions.MOVE_TO_BACKLOG:
                return await self.move_to_backlog(**kwargs)
            case JiraActions.ADD_COMMENT:
                return await self.add_comment_for_issue(**kwargs)
            case JiraActions.CREATE_ISSUE:
                raise NotImplementedError
            case JiraActions.ASSIGN_ISSUE:
                raise NotImplementedError
            case _:
                message = f'Invalid Jira action {action}!'
                logger.error(message)
                raise InvalidAction(message)

    async def get_list_projects(self):
        try:
            return await sync_to_async(self._connection.projects)
        except Exception as ex:
            message = f"Projects Getting Error! {ex}"
            logger.error(message)
            raise ProjectException(message)

    async def get_active_sprint(
            self,
            *,
            board_id: int,
            start: int | None = 0,
            size: int | None = 1,
            state: str | None = 'active'
    ):
        """
        Asynchronously retrieves the active sprint for a specified board, allowing optional pagination and state filtering.
        This method returns details of the active sprint based on the provided board ID and parameters.\

           parameters:
                board_id (int): The unique identifier of the board for which to retrieve the active sprint.
                start (int | None, optional): The index from which to start retrieving sprints, defaulting
                                             to 0 for the first item.
                size (int | None, optional): The maximum number of sprints to return, defaulting to 1.
                                             If set to None, all available sprints may be returned.
                state (str | None, optional): The state of the sprints to filter by, defaulting to 'active'.
                                                This can be used to specify different sprint states.

        """

        try:
            return await sync_to_async(self._connection.sprints,
                board_id=board_id,
                startAt=start,
                maxResults=size,
                state=state
            )
        except Exception as ex:
            message = f"Active Sprint Not Found! {ex}"
            logger.error(message)
            raise SprintException(message)

    async def create_sprint(
            self,
            *,
            name: str,
            board_id: int,
            start_date: Any | None = None,
            end_date: Any | None = None,
            description: str | None = None
    ):
        """
            Asynchronously creates a new sprint for the specified board, allowing optional start and end dates
            along with a description. This method initializes the sprint with the provided parameters to manage project
            workflows effectively.

            parameter:
                name (str): The name of the sprint to be created.
                board_id (int): The unique identifier of the board to which the sprint belongs.
                start_date (Any | None, optional): The start date of the sprint, which can be a datetime object or None. Defaults to None.
                end_date (Any | None, optional): The end date of the sprint, which can be a datetime object or None. Defaults to None.
                description (str | None, optional): A brief description of the sprint. Defaults to None.

        """

        try:
            return await sync_to_async(self._connection.create_sprint,
                name=name,
                board_id=board_id,
                startDate=start_date,
                endDate=end_date,
                goal=description
            )
        except Exception as ex:
            message = f"Sprint Creation Failed! {ex}"
            logger.error(message)
            raise SprintException(message)

    async def get_issue(
            self,
            *,
            issue_id: str
    ):
        """
        Asynchronously retrieves the details of a specific issue based on the provided issue ID.
        This method allows users to access issue information for further processing or display.

        parameter:
             issue_id (str): The unique identifier of the issue to be retrieved or processed.
        """
        try:
            res = await sync_to_async(self._connection.issue,id=issue_id)
            return res.raw
        except Exception as ex:
            message = f"Issue Not Found! {ex}"
            logger.error(message)
            raise SprintException(message)

    async def add_issue_to_sprint(
            self,
            *,
            board_id: int,
            issue_keys: list[str]
    ):
        """
            Asynchronously adds specified issues to a sprint associated with the given board ID.
            This method updates the sprint by including the provided issue keys for enhanced project tracking.

            parameter:
                issue_key (str): The unique identifier of the issue to which the comment will be added.
                board_id (int): The unique identifier of the board for which the operation will be performed.
        """

        try:
            current_sprint = await self.get_active_sprint(
                board_id=board_id
            )
            async for sprint in current_sprint:
                return await sync_to_async(self._connection.add_issues_to_sprint,
                    sprint_id=sprint.id,
                    issue_keys=issue_keys
                )
        except Exception as ex:
            message = f"Failed to add issue! {ex}"
            logger.error(message)
            raise TaskException(message)

    async def move_to_backlog(
            self,
            *,
            issue_keys: list[str]
    ):
        """
        Asynchronously moves specified issues to the backlog for better project management. This method
        allows users to update the status of the provided issue keys, ensuring they are set aside for future work.

        parameter:
            issue_key (str): The unique identifier of the issue to which the comment will be added.

        """
        try:
            return await sync_to_async(self._connection.move_to_backlog,
                issue_keys=issue_keys
            )
        except Exception as ex:
            message = f"Failed to move backlog! {ex}"
            logger.error(message)
            raise TaskException(message)

    async def add_comment_for_issue(
            self,
            *,
            issue_key: str,
            comments: str
    ):
        """
        Asynchronously adds a comment to the specified issue identified by the issue key.
        This method enhances collaboration by allowing users to provide feedback or updates directly on the issue.

            parameter:
                issue_key (str): The unique identifier of the issue to which the comment will be added.
                comments (str): The content of the comment to be added to the specified issue.

        """
        try:
            return await sync_to_async(self._connection.add_comment,
                issue=issue_key,
                body=comments
            )
        except Exception as ex:
            message = f"Comments added failed! {ex}"
            logger.error(message)
            raise TaskException(message)

    def __dir__(self):
        return (
            'list_projects',
            'active_sprint',
            'create_sprint',
            'get_issue',
            'add_issue_to_sprint',
            'move_to_backlog',
            'add_comment_for_issue'
        )
