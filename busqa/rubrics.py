# Bộ tiêu chí chấm điểm theo từng intent; tổng trọng số = 1.0
ALLOWED_INTENTS = [
    "đặt vé",
    "đổi vé",
    "hủy vé",
    "đổi chỗ",
    "hỏi thông tin"
]

RUBRICS = {
    "đặt vé": {
        "Xác thực & thu thập thông tin": 0.16,
        "Kiểm tra & xác nhận tình trạng chỗ/chuyến": 0.18,
        "Tư vấn lộ trình/giờ/ghế & upsell hợp lý": 0.12,
        "Giải thích giá/phí & chính sách": 0.14,
        "Hướng dẫn thanh toán & xác nhận đặt vé": 0.18,
        "Tác phong & rõ ràng": 0.10,
        "Tốc độ phản hồi": 0.12,
    },
    "đổi vé": {
        "Xác thực & điều kiện đổi": 0.18,
        "Kiểm tra chuyến thay thế phù hợp": 0.20,
        "Giải thích phí đổi & chính sách": 0.16,
        "Thực hiện/ghi nhận đổi (PNR mới/biên nhận)": 0.24,
        "Tác phong & rõ ràng": 0.12,
        "Tốc độ phản hồi": 0.10,
    },
    "hủy vé": {
        "Xác thực & điều kiện hủy": 0.20,
        "Giải thích chính sách hoàn/khấu trừ": 0.24,
        "Đề xuất phương án thay thế": 0.12,
        "Xử lý hoàn tiền/ghi nhận": 0.24,
        "Đồng cảm & ngôn ngữ phù hợp": 0.10,
        "Tốc độ phản hồi": 0.10,
    },
    "đổi chỗ": {
        "Xác thực & khả năng đổi theo sơ đồ ghế": 0.22,
        "Giải thích ràng buộc (loại ghế/phụ phí)": 0.16,
        "Đưa lựa chọn thay thế": 0.16,
        "Thực hiện/ghi nhận đổi chỗ": 0.24,
        "Tác phong & thái độ": 0.12,
        "Tốc độ phản hồi": 0.10,
    },
    "hỏi thông tin": {
        "Độ chính xác thông tin": 0.30,
        "Độ đầy đủ & chủ động": 0.24,
        "Hướng dẫn bước tiếp theo": 0.18,
        "Tác phong & thái độ": 0.14,
        "Tốc độ phản hồi": 0.14,
    },
}

LABEL_THRESHOLDS = [
    (90, "Xuất sắc"),
    (80, "Tốt"),
    (65, "Đạt"),
    (50, "Cần cải thiện"),
    (0,  "Kém"),
]