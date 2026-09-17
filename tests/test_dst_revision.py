import unittest
import numpy as np

from pipeline.dst_experiment import CompactDST, FEATURE_NAMES, RARE
from pipeline.model import Estimator, KEYS


class DSTRevisionTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.rows = [dict(pos='DST', x=rng.normal(size=len(FEATURE_NAMES)),
                          y=rng.uniform(0, 3, size=len(KEYS))) for _ in range(40)]

    def test_excluded_inputs_cannot_move_forecasts(self):
        model = CompactDST(0).fit(self.rows)
        changed = dict(self.rows[0], x=self.rows[0]['x'].copy())
        excluded = [i for i in range(len(FEATURE_NAMES)) if i not in model.features]
        changed['x'][excluded] += 10000
        np.testing.assert_array_equal(model.predict([self.rows[0]]), model.predict([changed]))

    def test_rare_events_use_training_prior_not_prediction_outcomes(self):
        model = CompactDST(0).fit(self.rows)
        changed = dict(self.rows[0], x=self.rows[0]['x']*100,
                       y=np.ones(len(KEYS))*9999)
        prediction = model.predict([changed])[0]
        for key in RARE:
            i = KEYS.index(key)
            self.assertAlmostEqual(prediction[i], np.mean([r['y'][i] for r in self.rows]))

    def test_other_position_models_unchanged(self):
        receivers = [dict(r, pos='WR') for r in self.rows]
        mixed = self.rows+receivers
        legacy = Estimator().fit(mixed).predict(receivers)
        revised = Estimator(dst_retention=0).fit(mixed).predict(receivers)
        np.testing.assert_array_equal(legacy, revised)


if __name__ == '__main__': unittest.main()
