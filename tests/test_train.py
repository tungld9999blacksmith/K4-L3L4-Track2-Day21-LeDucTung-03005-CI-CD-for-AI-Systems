import os
import json
import numpy as np
import pandas as pd
from src.train import train


FEATURE_NAMES = [
    "age", "workclass", "education_num", "marital_status", "occupation",
    "relationship", "sex", "capital_gain", "capital_loss", "hours_per_week",
]


def _make_temp_data(tmp_path):
    """
    Tao dataset nho voi cung schema Adult de su dung trong test.

    pytest cung cap `tmp_path` la mot thu muc tam thoi, tu dong xoa sau khi test ket thuc.
    Ham nay dung du lieu ngau nhien nen khong can ket noi cloud storage hay tai file CSV thuc.
    """
    rng = np.random.default_rng(0)
    n = 200

    # TODO 1: Tao mang X co kich thuoc (n, len(FEATURE_NAMES)) voi gia tri [0, 1)
    X = rng.random((n, len(FEATURE_NAMES)))

    # TODO 2: Tao mang y gom n phan tu nguyen ngau nhien trong [0, 2)
    y = rng.integers(0, 2, size=n)

    # TODO 3: Xay dung DataFrame, them cot "target"
    df = pd.DataFrame(X, columns=FEATURE_NAMES)
    df["target"] = y

    # TODO 4: Luu 160 dong dau lam tap huan luyen, 40 dong cuoi lam tap holdout
    train_path = str(tmp_path / "train.csv")
    eval_path = str(tmp_path / "holdout.csv")
    df.iloc[:160].to_csv(train_path, index=False)
    df.iloc[160:].to_csv(eval_path, index=False)

    # TODO 5: Tra ve (train_path, eval_path)
    return train_path, eval_path


def test_train_returns_float(tmp_path):
    """Kiem tra ham train() tra ve mot so thuc nam trong [0.0, 1.0]."""
    train_path, eval_path = _make_temp_data(tmp_path)

    # TODO 6: Goi ham train() voi sieu tham so nho
    f1 = train(
        {"n_estimators": 10, "learning_rate": 0.1, "max_depth": 2},
        data_path=train_path,
        eval_path=eval_path,
    )

    # TODO 7: Kiem tra ket qua
    assert isinstance(f1, float)
    assert 0.0 <= f1 <= 1.0


def test_report_file_created(tmp_path):
    """Kiem tra file outputs/report.json duoc tao sau khi huan luyen."""
    train_path, eval_path = _make_temp_data(tmp_path)
    train(
        {"n_estimators": 10, "learning_rate": 0.1, "max_depth": 2},
        data_path=train_path,
        eval_path=eval_path,
    )

    # TODO 8: Kiem tra file ton tai va noi dung dung dinh dang
    assert os.path.exists("outputs/report.json")
    with open("outputs/report.json") as f:
        report = json.load(f)
    assert "f1_score" in report
    assert "accuracy" in report


def test_model_file_created(tmp_path):
    """Kiem tra file models/model.joblib duoc tao sau khi huan luyen."""
    train_path, eval_path = _make_temp_data(tmp_path)
    train(
        {"n_estimators": 10, "learning_rate": 0.1, "max_depth": 2},
        data_path=train_path,
        eval_path=eval_path,
    )

    # TODO 9: Kiem tra file model ton tai
    assert os.path.exists("models/model.joblib")
