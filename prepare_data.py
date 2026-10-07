import pandas as pd
import os
import ssl

# UCI archive dang dung SSL certificate het han -> bo qua verify de tai duoc dataset cong khai.
# Chi dung cho nguon du lieu tin cay trong moi truong lab, khong dung cho production.
ssl._create_default_https_context = ssl._create_unverified_context

TRAIN_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
TEST_URL  = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test"

# 15 cot goc cua bo du lieu Adult (file CSV khong co dong tieu de)
RAW_COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education_num", "marital_status",
    "occupation", "relationship", "race", "sex", "capital_gain", "capital_loss",
    "hours_per_week", "native_country", "income",
]

# 10 dac trung duoc giu lai lam dau vao cho mo hinh
FEATURE_COLUMNS = [
    "age", "workclass", "education_num", "marital_status", "occupation",
    "relationship", "sex", "capital_gain", "capital_loss", "hours_per_week",
]

# Cac cot dang chuoi can ma hoa thanh so nguyen truoc khi huan luyen
CATEGORICAL_COLUMNS = ["workclass", "marital_status", "occupation", "relationship", "sex"]


def load(url: str, skiprows: int) -> pd.DataFrame:
    return pd.read_csv(
        url,
        header=None,
        names=RAW_COLUMNS,
        skiprows=skiprows,
        skipinitialspace=True,
        na_values="?",
    )


df_train = load(TRAIN_URL, skiprows=0)
df_test  = load(TEST_URL,  skiprows=1)   # dong dau cua adult.test la dong chu thich

# Nhan trong adult.test co dau cham o cuoi ("<=50K."), can cat bo cho khop voi adult.data
df_test["income"] = df_test["income"].str.rstrip(".")

df = pd.concat([df_train, df_test], ignore_index=True)

# Loai bo cac dong thieu gia tri (duoc danh dau bang "?" trong file goc)
df = df.dropna().reset_index(drop=True)

# Ma hoa cac cot phan loai thanh so nguyen theo thu tu bang chu cai
for col in CATEGORICAL_COLUMNS:
    df[col] = pd.Categorical(df[col]).codes

df["target"] = (df["income"] == ">50K").astype(int)
df = df[FEATURE_COLUMNS + ["target"]]
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

os.makedirs("data", exist_ok=True)

n_holdout = 500
n_half = (len(df) - n_holdout) // 2

holdout      = df.iloc[:n_holdout]
train_batch1 = df.iloc[n_holdout : n_holdout + n_half]
train_batch2 = df.iloc[n_holdout + n_half : n_holdout + 2 * n_half]

train_batch1.to_csv("data/train_batch1.csv", index=False)
holdout.to_csv("data/holdout.csv",           index=False)
train_batch2.to_csv("data/train_batch2.csv", index=False)

print(f"train_batch1.csv : {len(train_batch1)} mau")
print(f"holdout.csv      : {len(holdout)} mau")
print(f"train_batch2.csv : {len(train_batch2)} mau")
print(f"Ty le lop >50K   : {df['target'].mean():.1%}")
