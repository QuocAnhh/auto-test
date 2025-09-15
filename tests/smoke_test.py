# Simple smoke test for imports
def test_imports():
    import busqa.api_client
    import busqa.normalize
    import busqa.metrics
    import busqa.prompting
    import busqa.llm_client
    import busqa.evaluator
    import busqa.utils
    assert True

from busqa.metrics import compute_additional_metrics
from busqa.models import Message

def test_compute_additional_metrics():
    messages = [
        Message(ts=None, sender_type='user', sender_name=None, text='Tôi muốn đặt vé đi Hà Nội'),
        Message(ts=None, sender_type='agent', sender_name=None, text='Bạn cần đi ngày nào?'),
        Message(ts=None, sender_type='user', sender_name=None, text='Ngày mai'),
        Message(ts=None, sender_type='agent', sender_name=None, text='Bạn cần đi ngày nào?'),
        Message(ts=None, sender_type='agent', sender_name=None, text='Bạn cần đi ngày nào?'),
        Message(ts=None, sender_type='agent', sender_name=None, text='Các tuyến: A, B, C, D, E, F, G'),
    ]
    metrics = compute_additional_metrics(messages)
    assert metrics['repeated_questions'] >= 1
    assert metrics['agent_user_ratio'] > 1
    assert metrics['long_option_lists'] >= 1

