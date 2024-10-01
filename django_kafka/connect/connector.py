from abc import ABC, abstractmethod
from enum import StrEnum

from django_kafka.conf import settings
from django_kafka.exceptions import DjangoKafkaError
from django_kafka.connect.client import KafkaConnectClient

__all__ = [
    "Connector",
    "ConnectorStatus",
]


class ConnectorStatus(StrEnum):
    """
    https://docs.confluent.io/platform/current/connect/monitoring.html#connector-and-task-status
    UNASSIGNED: The connector/task has not yet been assigned to a worker.
    RUNNING: The connector/task is running.
    PAUSED: The connector/task has been administratively paused.
    FAILED: The connector/task has failed (usually by raising an exception, which is reported in the status output).
    """
    UNASSIGNED = "UNASSIGNED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class Connector(ABC):
    mark_for_removal = False

    @property
    def name(self) -> str:
        """Name of the connector."""
        return f"{settings.CLIENT_ID}.{self.__class__.__module__}.{self.__class__.__name__}"

    @property
    @abstractmethod
    def config(self) -> dict:
        """Configurations for the connector."""

    def __init__(self):
        self.client = KafkaConnectClient(
            host=settings.CONNECT["HOST"],
            auth=settings.CONNECT["AUTH"],
            retry=settings.CONNECT["RETRY"],
            timeout=settings.CONNECT["REQUESTS_TIMEOUT"],
        )

    def delete(self) -> bool:
        response = self.client.delete(self.name)

        if response.status_code == 404:
            return False

        if not response.ok:
            raise DjangoKafkaError(response.text)

        return True

    def submit(self) -> dict:
        response = self.client.update_or_create(self.name, self.config)

        if not response.ok:
            raise DjangoKafkaError(response.text)

        return response.json()

    def is_valid(self, raise_exception=False) -> bool:
        response = self.client.validate(self.config)

        if raise_exception and not response.ok:
            raise DjangoKafkaError(response.text)

        return response.ok

    def status(self) -> ConnectorStatus:
        response = self.client.connector_status(self.name)

        if not response.ok:
            raise DjangoKafkaError(response.text)

        return response.json()["connector"]["state"]