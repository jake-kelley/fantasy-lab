"""Load frozen per-position choices. Never tune during scheduled builds."""
import numpy as np
from .model import KEYS


class ConfiguredEstimator:
    def __init__(self, selection):self.selection=selection
    def fit(self, rows):
        from .tune_positions import make
        self.models={}
        for pos,choice in self.selection['positions'].items():
            selected=[r for r in rows if r['pos']==pos]
            self.models[pos]=make(pos,choice['selected']).fit(selected)
        return self
    def predict(self, rows):
        result=np.zeros((len(rows),len(KEYS)))
        for pos,model in self.models.items():
            ix=[i for i,r in enumerate(rows) if r['pos']==pos]
            if ix:result[ix]=model.predict([rows[i] for i in ix])
        return result
