"""Training-only selection of whole antibiotic blocks; missing is never an observed MIC."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from .data import IntegrityError


class DrugPanelSelector(TransformerMixin, BaseEstimator):
    def __init__(self, min_coverage=.2, correlation_threshold=.95, max_drugs=None, seed=42):
        self.min_coverage = min_coverage
        self.correlation_threshold = correlation_threshold
        self.max_drugs = max_drugs
        self.seed = seed

    def fit(self, X, y=None):
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        drugs = sorted(c.removesuffix('__missing') for c in X if c.endswith('__missing'))
        self.coverage_ = {d: float(X[d+'__missing'].eq(0).mean()) for d in drugs}
        usable = [d for d in drugs if self.coverage_[d] >= self.min_coverage]
        self.dropped_ = {d: 'low_training_coverage' for d in drugs if d not in usable}
        # Pairwise observed numeric bounds only; do not correlate imputed zero/missing values.
        representatives = {d: X[d+'__log2_bound'] for d in usable if d+'__log2_bound' in X}
        retained = []
        for drug in sorted(usable, key=lambda d: (-self.coverage_[d], d)):
            redundant = False
            if drug in representatives:
                for previous in retained:
                    if previous not in representatives:
                        continue
                    pairs = pd.concat([representatives[drug], representatives[previous]], axis=1).dropna()
                    if len(pairs) >= 10 and pairs.iloc[:, 0].nunique() > 1 and pairs.iloc[:, 1].nunique() > 1:
                        if abs(pairs.corr(method='spearman').iloc[0, 1]) >= self.correlation_threshold:
                            self.dropped_[drug] = 'training_correlation_with:' + previous
                            redundant = True
                            break
            if not redundant:
                retained.append(drug)
        if not retained:
            raise IntegrityError('No antibiotic has sufficient training-fold coverage; revise the planned panel.')
        self.importance_ = {}
        if self.max_drugs is not None and len(retained) > self.max_drugs:
            cols = [c for c in X if c.split('__')[0] in retained and '__' in c]
            values = SimpleImputer(strategy='median', keep_empty_features=True).fit_transform(X[cols])
            forest = RandomForestClassifier(n_estimators=80, max_depth=5, min_samples_leaf=3,
                                            random_state=self.seed, n_jobs=1).fit(values, y)
            self.importance_ = {d: float(sum(v for c, v in zip(cols, forest.feature_importances_) if c.startswith(d+'__'))) for d in retained}
            selected = sorted(retained, key=lambda d: (-self.importance_[d], d))[:self.max_drugs]
            self.dropped_.update({d: 'training_model_rank' for d in retained if d not in selected})
            retained = selected
        self.selected_drugs_ = sorted(retained)
        self.columns_ = [c for c in X if c == 'species' or ('__' in c and c.split('__')[0] in retained)]
        return self

    def transform(self, X):
        if not set(self.columns_) <= set(X):
            raise IntegrityError('Required selected panel columns are missing.')
        return X[self.columns_].copy()

    def get_feature_names_out(self, input_features=None):
        return np.array(self.columns_, dtype=object)

    def manifest(self):
        return {'fit_partition': 'training_only', 'selected_drugs': self.selected_drugs_,
                'training_coverage': self.coverage_, 'dropped_drugs': self.dropped_,
                'training_model_importance': self.importance_,
                'selection_settings': self.get_params()}
