from evals.run_eval import _confidence_report


def test_confidence_report_measures_selective_accuracy_and_coverage() -> None:
    rows = [
        {"confidence": 0.95, "category": ("A", "A")},
        {"confidence": 0.75, "category": ("B", "A")},
        {"confidence": 0.45, "category": ("C", "C")},
    ]

    report = _confidence_report(rows, (0.5, 0.8))

    assert report["0.50"] == {"tickets": 2, "coverage": 2 / 3, "category_accuracy": 0.5}
    assert report["0.80"] == {"tickets": 1, "coverage": 1 / 3, "category_accuracy": 1.0}


def test_confidence_report_handles_empty_accepted_set() -> None:
    report = _confidence_report([{"confidence": 0.2, "category": ("A", "A")}], (0.8,))

    assert report["0.80"] == {"tickets": 0, "coverage": 0.0, "category_accuracy": None}
