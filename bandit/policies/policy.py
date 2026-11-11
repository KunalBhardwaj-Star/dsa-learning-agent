from abc import ABC, abstractmethod
import numpy as np

class Policy(ABC):

    @abstractmethod
    def select_arm(self, context):
        pass

    @abstractmethod
    def update(self, arm, context, reward):
        pass