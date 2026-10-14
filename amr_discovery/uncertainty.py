"""Binomial intervals complement cluster bootstrap at perfect or zero outcomes."""
from scipy.stats import beta


def exact_interval(successes, total):
    if not total:
        return {'low': None, 'high': None, 'n': 0}
    return {'low': 0. if successes == 0 else float(beta.ppf(.025, successes, total-successes+1)),
            'high': 1. if successes == total else float(beta.ppf(.975, successes+1, total-successes)),
            'n': int(total), 'method': 'two-sided 95% Clopper-Pearson; assumes independent isolates'}
