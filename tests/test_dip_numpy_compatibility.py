import unittest
import warnings

import numpy as np
import torch
from torch import nn

from algorithms.response_strategy.DIP.DIP_ANN import predict_by_ann


class PredictionModel(nn.Module):
    device = torch.device("cpu")

    def forward(self, values):
        if torch.is_grad_enabled():
            raise AssertionError("Prediction must not build a training graph")
        return values * 0.5


class DIPNumpyCompatibilityTests(unittest.TestCase):
    def test_array_bounds_restore_numpy_values_without_deprecation(self):
        lower = np.array([-2.0, 1.0, 0.0])
        upper = np.array([2.0, 5.0, 10.0])
        values = np.array([[0.0, 3.0, 8.0], [2.0, 1.0, 2.0]])
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            result = predict_by_ann(PredictionModel(), values, lower, upper)
        self.assertIsInstance(result, np.ndarray)
        np.testing.assert_allclose(result, (values - lower) * 0.5 + lower)
        self.assertTrue(np.all(result >= lower))
        self.assertTrue(np.all(result <= upper))

    def test_scalar_bounds_keep_prediction_shape(self):
        values = np.array([[0.0, 1.0], [2.0, 3.0]])
        result = predict_by_ann(PredictionModel(), values, -1.0, 3.0)
        self.assertEqual(result.shape, values.shape)
        np.testing.assert_allclose(result, (values + 1.0) * 0.5 - 1.0)


if __name__ == "__main__":
    unittest.main()
