"""Shared application-layer ports and types."""

from app.shared.application.event_bus import EventHandler, IEventBus
from app.shared.application.repository import IRepository
from app.shared.application.result import Err, Ok, Result
from app.shared.application.unit_of_work import IUnitOfWork
from app.shared.application.use_case import UseCase

__all__ = [
    "Err",
    "EventHandler",
    "IEventBus",
    "IRepository",
    "IUnitOfWork",
    "Ok",
    "Result",
    "UseCase",
]
