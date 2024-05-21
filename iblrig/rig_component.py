from abc import abstractmethod

from iblrig.hardware_validation import Validator
from iblrig.pydantic_definitions import BunchModel


class RigComponent:
    @abstractmethod
    @property
    def pretty_name(self) -> str:
        """
        Get the pretty name of the component.

        Returns
        -------
        str
            A user-friendly name of the component.
        """
        ...

    @abstractmethod
    @property
    def validator(self) -> Validator:
        """
        Get the validator for the component.

        Returns
        -------
        Validator
            The validator instance associated with the component.
        """
        ...

    @abstractmethod
    @property
    def settings(self) -> BunchModel:
        """
        Get the settings for the component.

        Returns
        -------
        BunchModel
            The pydantic model for the component's settings.
        """
        ...
