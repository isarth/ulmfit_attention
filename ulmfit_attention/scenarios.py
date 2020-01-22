import abc
import torch
import numpy as np
from fastai.text import Learner, AWD_LSTM, DatasetType, accuracy
from typing import *
from .utils import RegisteredAbstractMeta, Configurable
from . import datasets
from . import training
from .learner import text_classifier_learner_custom


class Scenario(Configurable, metaclass=RegisteredAbstractMeta, is_registry=True):
    @staticmethod
    @abc.abstractmethod
    def single_run(params) -> Tuple[float, Dict, Optional[Learner]]:
        pass

    @classmethod
    def get_default_config(cls) -> Dict:
        return {}

    def __init__(self, **kwargs):
        """Allows for parameters to be passed, but used directly by components"""
        pass


class SmallTrainSample(Scenario):
    @staticmethod
    def single_run(params) -> Tuple[float, Dict, Optional[Learner]]:
        dp = params['scenario']['dataset']
        seed = params['seed']
        dataset = datasets.Dataset.from_config(dp)
        data_clas = dataset.get_training_sample(seed=seed)
        torch.manual_seed(seed)
        np.random.seed(seed)
        learn = text_classifier_learner_custom(data_clas, AWD_LSTM, params['aggregation'])
        _ = learn.load_encoder('fwd_enc')

        schedule = training.TrainingSchedule.from_config(params['training_schedule'])
        train_losses = []

        for phase in schedule.generate():
            learn.freeze_to(phase.freeze_to)
            learn.fit_one_cycle(**phase.to_dict())
            train_losses.append([float(x) for x in learn.recorder.losses])

        data_full = dataset.get_test_as_valid()
        learn.data = data_full
        pred, labels = learn.get_preds(DatasetType.Valid)

        # TODO: add options to include other metrics
        acc = float(accuracy(pred, labels))

        stats = {
            'train_losses': train_losses,
        }
        return acc, stats, learn