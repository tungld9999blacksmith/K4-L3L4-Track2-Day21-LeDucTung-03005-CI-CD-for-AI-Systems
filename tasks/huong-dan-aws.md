# Hướng Dẫn Làm Lab Với AWS

Tài liệu này thay thế các lệnh GCP mặc định trong [buoc-2.md](buoc-2.md) và [buoc-3.md](buoc-3.md) bằng phiên bản **AWS**. Phần logic (train, test, quality gate, CI/CD flow) giữ nguyên — chỉ đổi lớp hạ tầng cloud.

Bảng ánh xạ GCP → AWS dùng trong toàn bộ lab:

| Khái niệm | GCP (mặc định) | AWS (tài liệu này) |
|---|---|---|
| Object Storage | Google Cloud Storage (GCS) | **Amazon S3** |
| VM | Compute Engine (GCE) | **Amazon EC2** |
| CLI | `gcloud` / `gsutil` | **`aws`** |
| DVC storage extra | `dvc[gs]` | **`dvc[s3]`** |
| Cloud SDK Python | `google-cloud-storage` | **`boto3`** |
| Credentials | Service Account JSON | **IAM User Access Key** |
| URL remote DVC | `gs://bucket/dvc` | **`s3://bucket/dvc`** |

> Bước 1 ([buoc-1.md](buoc-1.md)) chạy hoàn toàn cục bộ, **không cần thay đổi gì** khi dùng AWS. Bắt đầu phần AWS từ mục 0 dưới đây.

---

## 0. Chuẩn Bị: Cài CLI Và Sửa Code Cho AWS

### 0.1 Cài AWS CLI và đăng nhập

```bash
# Kiểm tra đã cài chưa
aws --version          # cần AWS CLI v2

# Cấu hình credentials (nhập Access Key của IAM user ở mục 2.2)
aws configure
# AWS Access Key ID     : <ACCESS_KEY>
# AWS Secret Access Key : <SECRET_KEY>
# Default region name   : us-east-1
# Default output format : json
```

Nếu chưa có AWS CLI: tải tại https://aws.amazon.com/cli/ (Windows có file `.msi`).

### 0.1.1 (Windows) Chọn shell và chiến lược hai IAM user

- **Shell:** Toàn bộ hướng dẫn gốc dùng cú pháp **bash**. Trên Windows có hai lựa chọn:
  - **Git Bash**: chạy được y nguyên các lệnh bash (`export`, `cat <<EOF`, `chmod`...).
  - **PowerShell**: phải đổi cú pháp (`$VAR=` thay cho `export`, here-string `@"..."@` thay cho `<<EOF`). Các mục dưới có sẵn bản PowerShell.
- **Hai IAM user, hai vai trò khác nhau** (đừng nhầm lẫn — đây là lỗi hay gặp nhất):
  - `ai-lab-user` = **người thao tác** (tạo bucket, tạo EC2). Cần quyền rộng: gắn `AmazonS3FullAccess` + `AmazonEC2FullAccess` (hoặc `AdministratorAccess`). **Giữ user này làm profile `default`** của `aws configure`.
  - `income-lab-user` = **danh tính CI/CD** (least-privilege, chỉ S3 trên đúng 1 bucket). **Không** nạp vào CLI local; chỉ dùng cho **GitHub Secrets** và (tùy chọn) cho DVC.
  - ⚠️ Nếu lỡ `aws configure` đè `default` bằng key của `income-lab-user`, bạn sẽ bị `AccessDenied` khi tạo bucket/EC2. Khi đó chạy `aws configure` lại, nhập key của `ai-lab-user`, và xác nhận bằng `aws sts get-caller-identity` (phải thấy `.../user/ai-lab-user`).

### 0.2 Sửa `requirements.txt`

`requirements.txt` sinh từ `pip freeze` trên Windows có vài vấn đề làm **fail CI trên ubuntu-latest**, cần sửa:

| Vấn đề | Cách sửa |
|---|---|
| File lưu dạng **UTF-16** | Lưu lại thành **UTF-8/ASCII** (pip đọc ổn định hơn) |
| `pywin32==312` (chỉ chạy Windows) | **Xóa dòng này** — Linux không cài được, `pip install` sẽ fail |
| `google-cloud-storage==...` (SDK của GCP) | Xóa (không dùng với AWS) |
| Thiếu `boto3` | **Thêm `boto3`** — `serve.py` và bước upload model trong CI đều `import boto3` |
| DVC chưa có extra S3 | Đảm bảo có `dvc-s3` (và `s3fs`); nếu dùng `dvc==3.50.1` thì `pip install dvc-s3` |

Lưu ý version: `boto3` và `botocore` phải **cùng số version**. Nếu `botocore==1.43.106` thì dùng `boto3==1.43.106`. Kiểm tra không xung đột bằng:

```bash
pip install --dry-run boto3==1.43.106 botocore==1.43.106 s3fs dvc-s3
```

Sau khi sửa, cài lại:

```bash
pip install -r requirements.txt
```

> Gợi ý (tùy chọn): tách `requirements.local.txt` (đầy đủ gói để chạy local) khỏi `requirements.txt` (gọn, chỉ gói cần cho CI) để pipeline cài nhanh và tránh gói Windows-only.

### 0.3 Sửa `src/serve.py` dùng boto3 thay cho google.cloud.storage

Thay phần import và hàm `download_model()`. Phần endpoint `/healthz` và `/score` giữ nguyên.

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3                    # thay cho: from google.cloud import storage
import joblib
import os

app = FastAPI()

ARTIFACT_BUCKET = os.environ["ARTIFACT_BUCKET"]
MODEL_KEY = "artifacts/current/model.joblib"
MODEL_PATH = os.path.expanduser("~/models/model.joblib")


def download_model():
    """Tải model.joblib từ S3 về máy khi server khởi động.

    Xác thực lấy tự động từ IAM instance role hoặc biến môi trường
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (đặt trong systemd service).
    """
    s3 = boto3.client("s3")
    s3.download_file(ARTIFACT_BUCKET, MODEL_KEY, MODEL_PATH)
    print("Model da duoc tai xuong tu S3.")
```

Những phần còn lại của `serve.py` (`download_model()` được gọi, `healthz`, `score`, khối `__main__`) **không đổi**.

---

## 2.1 (AWS) Tạo S3 Bucket

Tên bucket phải là duy nhất toàn cầu. Thay `<BUCKET_NAME>` bằng tên của bạn (ví dụ `income-lab-tung-2026`).

**Git Bash:**
```bash
export BUCKET=<BUCKET_NAME>
export REGION=us-east-1
aws s3 mb s3://$BUCKET --region $REGION
```

**PowerShell:**
```powershell
$BUCKET = "<BUCKET_NAME>"
$REGION = "us-east-1"
aws s3 mb "s3://$BUCKET" --region $REGION
```

Xác nhận bucket đã tạo (dùng `head-bucket` thay cho `aws s3 ls`, vì `ai-lab-user` có thể không có quyền `ListAllMyBuckets`):

```bash
aws s3api head-bucket --bucket <BUCKET_NAME>    # không lỗi = tồn tại & truy cập được
```

> Nếu `aws s3 mb` báo `AccessDenied ... s3:CreateBucket`: `ai-lab-user` chưa đủ quyền. Vào AWS Console (root/admin) gắn `AmazonS3FullAccess` (+ `AmazonEC2FullAccess`) cho user này rồi chạy lại.

---

## 2.2 (AWS) Tạo IAM User Và Access Key

Thay cho Service Account JSON của GCP, AWS dùng IAM user + access key. Theo nguyên tắc quyền tối thiểu: chỉ cấp quyền đọc/ghi **trên đúng bucket này**, không cấp toàn quyền S3.

```bash
# 1. Tạo IAM user
aws iam create-user --user-name income-lab-user

# 2. Tạo policy quyền tối thiểu chỉ trên bucket của bạn
cat > /tmp/income-lab-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::$BUCKET"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::$BUCKET/*"
    }
  ]
}
EOF

aws iam put-user-policy \
  --user-name income-lab-user \
  --policy-name income-lab-s3 \
  --policy-document file:///tmp/income-lab-policy.json

# 3. Tạo access key (LƯU LẠI ngay — secret chỉ hiện một lần)
aws iam create-access-key --user-name income-lab-user
```

Kết quả trả về chứa `AccessKeyId` và `SecretAccessKey`. **Lưu lại cả hai** — bạn cần cho `aws configure` (mục 0.1) và cho GitHub Secrets (mục 2.9).

> Khác với GCP không có file `sa-key.json` để lo commit nhầm. Nhưng **tuyệt đối không** dán Access Key vào code hay commit lên git.

---

## 2.3 (AWS) Cài Đặt DVC Với S3 Remote

```bash
dvc init

# Trỏ DVC đến S3
dvc remote add -d labstore s3://$BUCKET/dvc

# AWS: DVC tự đọc credentials từ ~/.aws/credentials (do `aws configure` tạo)
# hoặc từ biến môi trường AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
# Không cần dòng `dvc remote modify ... credentialpath` như GCP.
dvc remote modify labstore region $REGION

# Theo dõi dữ liệu
dvc add data/train_batch1.csv
dvc add data/holdout.csv
dvc add data/train_batch2.csv

# Commit con trỏ DVC (KHÔNG commit file CSV)
git add data/train_batch1.csv.dvc data/holdout.csv.dvc data/train_batch2.csv.dvc \
        .gitignore .dvc/config
git commit -m "feat: track datasets with DVC (S3 remote)"

# Đẩy CSV lên S3
dvc push
```

Xác nhận trên S3:

```bash
aws s3 ls s3://$BUCKET/dvc/ --recursive
```

---

## 2.4 (AWS) Tạo EC2 Instance

Cần: một key pair SSH, một security group mở cổng 22 (SSH) và 8080 (API).

```bash
# 1. Tạo key pair để SSH vào EC2 (lưu file .pem, chmod 400)
aws ec2 create-key-pair --key-name income-key \
  --query 'KeyMaterial' --output text > income-key.pem
chmod 400 income-key.pem

# 2. Tạo security group
aws ec2 create-security-group \
  --group-name income-api-sg \
  --description "Income API lab"

# Lấy group id
export SG=$(aws ec2 describe-security-groups \
  --group-names income-api-sg \
  --query 'SecurityGroups[0].GroupId' --output text)

# 3. Mở cổng 22 (SSH) và 8080 (API) cho mọi IP (lab; production nên giới hạn IP)
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG \
  --protocol tcp --port 8080 --cidr 0.0.0.0/0

# 4. Khởi chạy instance Ubuntu 22.04 (free tier: t2.micro / t3.micro)
#    AMI id khác nhau theo region — lệnh dưới tự tra AMI Ubuntu 22.04 mới nhất.
export AMI=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId' --output text)

aws ec2 run-instances \
  --image-id $AMI \
  --instance-type t3.micro \
  --key-name income-key \
  --security-group-ids $SG \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=income-api}]'

# 5. Lấy IP công khai (lưu lại cho GitHub Secrets SERVER_HOST)
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=income-api" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

Ghi lại IP công khai vừa in ra.

### 2.4 (Windows / PowerShell)

Khác biệt quan trọng trên Windows: **không** dùng `>` hay `Out-File` để lưu private key — chúng tạo file UTF-16/CRLF làm hỏng key. Dùng `WriteAllText` (UTF-8 không BOM, LF) như dưới.

```powershell
# 1. Key pair -> lưu income-key.pem đúng định dạng
$keyLines = aws ec2 create-key-pair --key-name income-key --query 'KeyMaterial' --output text
$key = ($keyLines -join "`n") + "`n"
[System.IO.File]::WriteAllText("$PWD\income-key.pem", $key, [System.Text.UTF8Encoding]::new($false))

# Sửa quyền để Windows OpenSSH chấp nhận (tương đương chmod 400)
icacls income-key.pem /inheritance:r
icacls income-key.pem /grant:r "$($env:USERNAME):R"

# 2. Security group + mở cổng 22 và 8080
aws ec2 create-security-group --group-name income-api-sg --description "Income API lab"
$SG = (aws ec2 describe-security-groups --group-names income-api-sg --query 'SecurityGroups[0].GroupId' --output text).Trim()
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 8080 --cidr 0.0.0.0/0

# 3. AMI Ubuntu 22.04 mới nhất
$AMI = (aws ec2 describe-images --owners 099720109477 --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" "Name=state,Values=available" --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId' --output text).Trim()

# 4. Launch instance
aws ec2 run-instances --image-id $AMI --instance-type t3.micro --key-name income-key --security-group-ids $SG --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=income-api}]'

# 5. Lấy Public IP (chờ ~30-60s cho instance running)
aws ec2 describe-instances --filters "Name=tag:Name,Values=income-api" "Name=instance-state-name,Values=running" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

Lưu ý: chạy cả 5 bước trong **cùng một cửa sổ** PowerShell (biến `$SG`, `$AMI` là tạm). File `income-key.pem` nằm trong thư mục project và đã được `.gitignore` chặn (`*.pem`).

---

## 2.5 (AWS) Cấu Hình EC2 (Một Lần, Thủ Công)

> **Windows/PowerShell:** `ssh` và `scp` có sẵn trong Windows OpenSSH nên dùng y như bash, chỉ cần đặt biến kiểu PowerShell: `$VM_IP = "<PUBLIC_IP>"` và tham chiếu `$VM_IP`. Riêng lệnh ở mục 2.8 dùng `$(cat ...)` (bash) — xem bản PowerShell ngay trong mục đó.

SSH vào EC2 (user mặc định của Ubuntu AMI là `ubuntu`):

```bash
export VM_IP=<PUBLIC_IP_VUA_LAY>       # PowerShell: $VM_IP = "<PUBLIC_IP>"
ssh -i income-key.pem ubuntu@$VM_IP
```

Bên trong EC2, cài thư viện:

```bash
sudo apt update && sudo apt install -y python3-pip
pip3 install fastapi uvicorn scikit-learn joblib boto3

mkdir -p ~/models ~/src
```

> **Khác GCP:** GCP cần copy `sa-key.json` lên VM. Với AWS, bạn **không** copy access key lên EC2. Thay vào đó đặt `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` trong systemd service (mục 2.7), hoặc tốt hơn là gắn **IAM instance role** cho EC2 (xem ghi chú cuối mục 2.7).

Thoát SSH, rồi copy `serve.py` lên EC2:

```bash
scp -i income-key.pem src/serve.py ubuntu@$VM_IP:~/src/serve.py
```

---

## 2.6 (AWS) Viết `src/serve.py`

Dùng phiên bản boto3 đã nêu ở **mục 0.3**. Phần `/healthz` và `/score` làm theo đúng TODO trong [buoc-2.md](buoc-2.md) mục 2.6 — logic không đổi.

---

## 2.7 (AWS) Cấu Hình Systemd Service Trên EC2

SSH trở lại EC2:

```bash
ssh -i income-key.pem ubuntu@$VM_IP
```

Tạo service (chú ý biến môi trường AWS thay cho `GOOGLE_APPLICATION_CREDENTIALS`):

```bash
sudo tee /etc/systemd/system/income-api.service > /dev/null <<EOF
[Unit]
Description=Income Model Inference Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment="ARTIFACT_BUCKET=<YOUR_BUCKET_NAME>"
Environment="AWS_ACCESS_KEY_ID=<ACCESS_KEY>"
Environment="AWS_SECRET_ACCESS_KEY=<SECRET_KEY>"
Environment="AWS_DEFAULT_REGION=us-east-1"
ExecStart=/usr/bin/python3 /home/ubuntu/src/serve.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable income-api
```

Thay `<YOUR_BUCKET_NAME>`, `<ACCESS_KEY>`, `<SECRET_KEY>` bằng giá trị thật. Chưa khởi động service lúc này — model chưa có trên S3 cho tới khi pipeline chạy lần đầu.

> **Cách an toàn hơn (khuyến nghị):** thay vì nhúng access key vào service, gắn IAM instance role có policy S3 giống mục 2.2 vào EC2. Khi đó boto3 tự lấy credential tạm thời, và bạn xóa hai dòng `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` khỏi service.

---

## 2.8 (AWS) SSH Key Cho GitHub Actions Deploy

Phần này **giống hệt GCP**. Tạo key deploy riêng (khác với `income-key.pem` dùng để bạn SSH thủ công):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/income_deploy -N "" -C "github-actions-deploy"
```

Thêm public key vào EC2:

**Git Bash:**
```bash
ssh -i income-key.pem ubuntu@$VM_IP \
  "echo '$(cat ~/.ssh/income_deploy.pub)' >> ~/.ssh/authorized_keys"
```

**PowerShell:**
```powershell
$PUB = Get-Content "$HOME\.ssh\income_deploy.pub"
ssh -i income-key.pem ubuntu@$VM_IP "echo '$PUB' >> ~/.ssh/authorized_keys"
```

---

## 2.9 (AWS) GitHub Secrets

Vào repo: Settings > Secrets and variables > Actions. Thêm 5 secrets:

| Tên secret | Giá trị (AWS) |
|---|---|
| STORAGE_CREDENTIALS | JSON: `{"aws_access_key_id":"<ACCESS_KEY>","aws_secret_access_key":"<SECRET_KEY>"}` |
| ARTIFACT_BUCKET | Tên bucket S3 (ví dụ `income-lab-tung-2026`) |
| SERVER_HOST | IP công khai của EC2 (mục 2.4) |
| SERVER_USER | `ubuntu` (user mặc định của Ubuntu AMI) |
| SERVER_SSH_KEY | Toàn bộ nội dung `~/.ssh/income_deploy` (private key) |

---

## 2.11 (AWS) Điền `.github/workflows/cicd.yml`

Chỉ hai TODO khác với GCP: **TODO 2 (xác thực)** và **TODO 5 (upload model)**. Các TODO còn lại (pytest, dvc pull, read f1, quality gate, SSH deploy) giữ nguyên.

**TODO 2 — Authenticate to Cloud Storage (AWS):**

```yaml
      - name: Authenticate to S3
        run: |
          echo "AWS_ACCESS_KEY_ID=$(echo '${{ secrets.STORAGE_CREDENTIALS }}' | python -c 'import sys,json; print(json.load(sys.stdin)["aws_access_key_id"])')" >> $GITHUB_ENV
          echo "AWS_SECRET_ACCESS_KEY=$(echo '${{ secrets.STORAGE_CREDENTIALS }}' | python -c 'import sys,json; print(json.load(sys.stdin)["aws_secret_access_key"])')" >> $GITHUB_ENV
          echo "AWS_DEFAULT_REGION=us-east-1" >> $GITHUB_ENV
```

**TODO 3 — Pull data with DVC (giống GCP):**

```yaml
      - name: Pull data with DVC
        run: dvc pull data/train_batch1.csv.dvc data/holdout.csv.dvc
```

**TODO 5 — Upload model to S3 (boto3):**

```yaml
      - name: Upload model to S3
        run: |
          python - <<'PYEOF'
          import boto3, os
          bucket = os.environ["ARTIFACT_BUCKET"]
          boto3.client("s3").upload_file(
              "models/model.joblib", bucket, "artifacts/current/model.joblib"
          )
          print("Model uploaded to S3.")
          PYEOF
        env:
          ARTIFACT_BUCKET: ${{ secrets.ARTIFACT_BUCKET }}
```

Các TODO còn lại điền theo gợi ý sẵn trong [buoc-2.md](buoc-2.md) mục 2.11 (không phụ thuộc provider).

---

## 2.12 (AWS) Chạy Pipeline Lần Đầu Và Khởi Động Service

Sau khi push code và pipeline chạy xanh (model đã lên S3), khởi động service trên EC2:

```bash
ssh -i income-key.pem ubuntu@$VM_IP "sudo systemctl start income-api"
```

Thử endpoint:

```bash
curl http://$VM_IP:8080/healthz

curl -X POST http://$VM_IP:8080/score \
  -H "Content-Type: application/json" \
  -d '{"features": [28, 2, 14, 2, 11, 0, 1, 0, 0, 45]}'
```

---

## Bước 3 (AWS) Huấn Luyện Liên Tục

Toàn bộ [buoc-3.md](buoc-3.md) giữ nguyên. Chỉ một chỗ khác: nếu cần đặt lại credential thủ công trước `dvc push` (mục 3.3 / xử lý sự cố), dùng:

```bash
export AWS_ACCESS_KEY_ID=<ACCESS_KEY>
export AWS_SECRET_ACCESS_KEY=<SECRET_KEY>
dvc push
```

(thay cho `export GOOGLE_APPLICATION_CREDENTIALS=sa-key.json` của GCP). Thông thường không cần, vì `aws configure` đã lưu credential vào `~/.aws/credentials`.

---

## Ảnh Nộp Bài (AWS)

Yêu cầu không đổi, chỉ khác console:

| Tên file | Nội dung (AWS) |
|---|---|
| `05-cloud-storage.png` | **S3 Console** hiển thị prefix `dvc/` và `artifacts/current/model.joblib` (thay cho GCS Console) |

Bốn ảnh còn lại (`01`–`04`) giống hệt bản GCP.

---

## Xử Lý Sự Cố (AWS)

**`dvc push` lỗi `NoCredentialsError` / `Access Denied`**
Chạy `aws configure` lại, hoặc `aws sts get-caller-identity` để xác nhận đang dùng đúng IAM user. Kiểm tra policy ở mục 2.2 trỏ đúng tên bucket.

**`dvc pull` trong GitHub Actions thất bại**
Xác nhận secret `STORAGE_CREDENTIALS` là JSON hợp lệ với đúng 2 khóa `aws_access_key_id` và `aws_secret_access_key`, và region trong `.dvc/config` khớp với region bucket.

**Không SSH được vào EC2 (Connection timed out)**
Security group phải mở cổng 22 từ IP của bạn. Dùng đúng user `ubuntu` và file `income-key.pem` (đã `chmod 400`).

**Service EC2 không khởi động (`boto3.exceptions` / AccessDenied khi tải model)**
Kiểm tra `ARTIFACT_BUCKET` và các biến `AWS_*` trong file service đúng chưa, và IAM user/role có quyền `s3:GetObject` trên bucket. Xem log: `sudo journalctl -u income-api -n 50`.

---

## Dọn Dẹp Để Tránh Tốn Phí (sau khi chấm điểm)

```bash
# Dừng và xóa EC2
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>

# Xóa object trong bucket rồi xóa bucket
aws s3 rm s3://$BUCKET --recursive
aws s3 rb s3://$BUCKET

# Xóa IAM access key và user
aws iam delete-access-key --user-name income-lab-user --access-key-id <ACCESS_KEY>
aws iam delete-user-policy --user-name income-lab-user --policy-name income-lab-s3
aws iam delete-user --user-name income-lab-user
```
