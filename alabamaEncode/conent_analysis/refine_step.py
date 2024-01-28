from abc import abstractmethod, ABC


class RefineStep(ABC):
    @abstractmethod
    def __call__(self, ctx, sequence):
        pass
