# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

<!--
HƯỚNG DẪN - đọc rồi XÓA TOÀN BỘ các khối chú thích này sau khi điền xong:

  - Giới hạn: KHÔNG QUÁ 1 TRANG A4, tương đương khoảng 450 - 550 từ nội dung.
  - Chỉ điền vào các chỗ ___ và các ô trong bảng. Không thêm mục mới.
  - Viết bằng câu hoàn chỉnh, không gạch đầu dòng cụt lủn.
  - Kiểm tra độ dài sau khi đã xóa hết chú thích:
        wc -w nop-bai/bao-cao.md
    và xem trước bản in bằng cách mở file trên GitHub rồi Ctrl+P / Cmd+P.
-->

| | |
|---|---|
| Họ và tên | Lê Đức Tùng |
| MSSV | 2A202603005 |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/___/___ |
| Ngày nộp | 7/10/2026 |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

<!-- Khoảng 120 - 150 từ. Điền kết quả thật từ MLflow UI ở Bước 1, tối thiểu 3 lần chạy. -->

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---|---|---|---|---|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |

**Bộ siêu tham số đã chọn:** `n_estimators=200`, `learning_rate=0.1`, `max_depth=5`.

**Lý do:** Tôi chọn lần chạy 3 vì nó đạt `f1_score` cao nhất (0.7149), vượt ngưỡng 0.65 mà
pipeline Bước 2 yêu cầu. Điều đáng chú ý là lần chạy có accuracy cao nhất lại là lần 1
(0.8780) chứ không phải lần có f1 cao nhất, cho thấy accuracy không phản ánh đúng khả năng
bắt được lớp thu nhập cao và không thể dùng làm căn cứ chọn mô hình. Lần chạy 2 với
`n_estimators` nhỏ, `learning_rate` thấp và cây nông nhất cho f1 chỉ 0.6051 — dưới ngưỡng và
sẽ bị chặn triển khai. Qua đó thấy rõ đánh đổi giữa `n_estimators` và `learning_rate`: khi cả
hai đều nhỏ, mô hình học quá ít và bỏ sót lớp dương; tăng số cây kèm cây sâu hơn (lần 3) giúp
mô hình bù lại và cải thiện f1 rõ rệt trong khi accuracy gần như không đổi.

<!--
Trả lời trong phần Lý do:
  - Vì sao bộ này tốt hơn các bộ còn lại (dựa trên f1_score, không phải accuracy)?
  - Lần chạy có accuracy cao nhất có trùng với lần có f1_score cao nhất không?
    Nếu không, điều đó nói lên điều gì?
  - Bạn quan sát thấy đánh đổi nào giữa n_estimators và learning_rate?
-->

---

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

<!-- Khoảng 120 - 150 từ. -->

Tập dữ liệu Adult mất cân bằng: chỉ khoảng 24,8% số mẫu thuộc lớp thu nhập trên 50K, còn lại
75,2% là thu nhập thấp. Hệ quả là một mô hình "lười" luôn trả lời thu nhập thấp cho mọi mẫu
vẫn đạt accuracy khoảng 0,752 — con số nghe cao nhưng gây hiểu nhầm, vì mô hình đó không bắt
được bất kỳ trường hợp thu nhập cao nào (f1 của lớp dương bằng 0) và hoàn toàn vô dụng với
mục tiêu bài toán. F1 của lớp dương là trung bình điều hòa của precision và recall trên đúng
lớp thu nhập cao, nên nó đo được khả năng vừa tìm đúng vừa tìm đủ các trường hợp mà accuracy
che giấu. Vì vậy không được truyền `average="weighted"` hay `average="macro"` khi gọi
`f1_score`: các giá trị đó bị lớp đa số kéo lên cao, làm mất ý nghĩa của ngưỡng 0,65 và khiến
một mô hình kém vẫn vượt qua được cổng chất lượng.

<!--
Cần nêu được:
  - Phân bố lớp của tập dữ liệu (tỷ lệ lớp thu nhập > 50K) và hệ quả của nó.
  - Accuracy của một mô hình luôn trả lời "thu nhập thấp" là bao nhiêu, vì sao con số
    đó gây hiểu nhầm.
  - F1 của lớp dương đo điều gì mà accuracy không đo được.
  - Vì sao KHÔNG dùng average="weighted" hay average="macro" khi gọi f1_score.
-->

---

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết

<!-- Nêu 2 - 3 khó khăn thật, mỗi ô một câu ngắn. -->

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| ___ | ___ | ___ |
| ___ | ___ | ___ |
| ___ | ___ | ___ |

---

## 4. So Sánh Bước 2 và Bước 3 (bắt buộc, 2 - 3 câu)

<!-- Lấy số liệu từ bảng ở mục 3.6 của tasks/buoc-3.md. -->

| | f1_score | accuracy |
|---|---|---|
| Bước 2 (chỉ `train_batch1`) | ___ | ___ |
| Bước 3 (thêm `train_batch2`) | ___ | ___ |

**Nhận xét:** ___

<!--
Một câu trả lời trung thực kiểu "f1 giảm 0,01 vì dữ liệu mới cùng phân phối, không mang
thêm thông tin mới" được đánh giá cao hơn kết luận sai rằng thêm dữ liệu luôn tốt hơn.
-->

---

## 5. Phần Bonus Đã Thực Hiện (nếu có)

<!-- Xóa cả mục 5 nếu không làm bonus. Mỗi bonus tối đa 1 dòng. -->

- [ ] Bonus 1 - Tracking MLflow từ xa với DagsHub: ___
- [ ] Bonus 2 - Điều chỉnh ngưỡng quyết định: ___
- [ ] Bonus 3 - Báo cáo precision / recall tự động: ___
- [ ] Bonus 4 - Hoàn trả về phiên bản trước: ___
- [ ] Bonus 5 - Cảnh báo lệch lạc dữ liệu: ___
