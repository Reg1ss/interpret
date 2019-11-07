# Copyright (c) 2019 Microsoft Corporation

# Distributed under the MIT software license
# TODO: Test EBMUtils

# from scipy.special import expit
from sklearn.utils.extmath import softmax
import numbers
import numpy as np


import logging

log = logging.getLogger(__name__)


# TODO: Clean up
class EBMUtils:
    @staticmethod
    def get_count_scores_c(n_classes):
        # this should reflect how the C code represents scores
        return 1 if n_classes <= 2 else n_classes

    @staticmethod
    def gen_features(col_types, col_n_bins):
        # Create Python form of features
        # Undocumented.
        features = [None] * len(col_types)
        for col_idx, _ in enumerate(features):
            features[col_idx] = {
                # NOTE: Ordinal only handled at native, override.
                # 'type': col_types[col_idx],
                "type": "continuous",
                # NOTE: Missing not implemented at native, always set to false.
                "has_missing": False,
                "n_bins": col_n_bins[col_idx],
            }
        return features

    @staticmethod
    def gen_feature_combinations(feature_indices):
        feature_combinations = [None] * len(feature_indices)
        for i, indices in enumerate(feature_indices):
            # TODO PK v.2 remove n_attributes (this is the only place it is used, but it's public)
            # TODO PK v.2 rename all instances of "attributes" -> "features"
            feature_combination = {"n_attributes": len(indices), "attributes": indices}
            feature_combinations[i] = feature_combination
        return feature_combinations

    @staticmethod
    def scores_by_feature_combination(
        X, feature_combinations, model, skip_feature_combination_idxs=[]
    ):
        for set_idx, feature_combination in enumerate(feature_combinations):
            if set_idx in skip_feature_combination_idxs:
                continue
            tensor = model[set_idx]

            # Get the current column(s) to process
            feature_idxs = feature_combination["attributes"]
            feature_idxs = list(reversed(feature_idxs))
            sliced_X = X[:, feature_idxs]
            scores = tensor[tuple(sliced_X.T)]

            yield set_idx, feature_combination, scores

    @staticmethod
    def decision_function(
        X, feature_combinations, model_feature_combinations, intercept, skip_feature_combination_idxs=[]
    ):
        if X.ndim == 1:
            X = X.reshape(1, X.shape[0])

        # Initialize empty vector for predictions
        if isinstance(intercept, numbers.Number) or len(intercept) == 1:
            score_vector = np.zeros(X.shape[0])
        else:
            score_vector = np.zeros((X.shape[0], len(intercept)))

        score_vector += intercept

        scores_gen = EBMUtils.scores_by_feature_combination(
            X, feature_combinations, model_feature_combinations, skip_feature_combination_idxs
        )
        for _, _, scores in scores_gen:
            score_vector += scores

        if not np.all(np.isfinite(score_vector)):  # pragma: no cover
            msg = "Non-finite values present in log odds vector."
            log.error(msg)
            raise Exception(msg)

        return score_vector

    @staticmethod
    def classifier_predict_proba(X, attribute_sets_, attribute_set_models_, intercept_, skip_feature_combination_idxs=[]):
        log_odds_vector = EBMUtils.decision_function(
            X,
            attribute_sets_,
            attribute_set_models_,
            intercept_,
            skip_feature_combination_idxs,
        )

        # Handle binary classification case -- softmax only works with 0s appended
        if log_odds_vector.ndim == 1:
            decision_2d = np.c_[np.zeros(log_odds_vector.shape), log_odds_vector]
        else:
            decision_2d = log_odds_vector
        return softmax(decision_2d)

    @staticmethod
    def classifier_predict(X, attribute_sets_, attribute_set_models_, intercept_, classes_):
        scores = EBMUtils.classifier_predict_proba(X, attribute_sets_, attribute_set_models_, intercept_)
        return classes_[np.argmax(scores, axis=1)]

    @staticmethod
    def regressor_predict(X, attribute_sets_, attribute_set_models_, intercept_, skip_feature_combination_idxs=[]):
        scores = EBMUtils.decision_function(
            X,
            attribute_sets_,
            attribute_set_models_,
            intercept_,
            skip_feature_combination_idxs,
        )
        return scores

    @staticmethod
    def gen_feature_name(feature_idxs, col_names):
        feature_name = []
        for feature_index in feature_idxs:
            feature_name.append(col_names[feature_index])
        feature_name = " x ".join(feature_name)
        return feature_name

    @staticmethod
    def gen_feature_type(feature_idxs, col_types):
        if len(feature_idxs) == 1:
            return col_types[feature_idxs[0]]
        else:
            return "pairwise"
