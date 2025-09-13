# Simple smoke test for imports
def test_imports():
    import busqa.api_client as a
    import busqa.normalize as n
    import busqa.metrics as m
    import busqa.prompting as p
    import busqa.llm_client as l
    import busqa.evaluator as e
    import busqa.rubrics as r
    import busqa.utils as u
    assert True