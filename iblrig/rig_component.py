from abc import ABC, abstractmethod

from pydantic import BaseModel

from iblrig.hardware_validation import Validator


class RigComponent(ABC):
    @property
    @abstractmethod
    def pretty_name(self) -> str:
        """
        Get the component's pretty name.

        Returns
        -------
        str
            A user-friendly name of the component.
        """
        ...

    @property
    @abstractmethod
    def validator(self) -> Validator:
        """
        Get the component's validator.

        Returns
        -------
        Validator
            The validator instance associated with the component.
        """
        ...

    @property
    @abstractmethod
    def settings(self) -> BaseModel:
        """
        Get the component's settings.

        Returns
        -------
        BaseModel
            The pydantic model for the component's settings.
        """
        ...
