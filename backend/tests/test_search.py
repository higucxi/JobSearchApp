import pytest
from app.utils import extract_exclusion_terms, tokenize_for_search

class TestSearchParsing:
    """Test search query parsing."""

    def test_simple_query(self):
        query, exclusions = extract_exclusion_terms("python")
        assert query == "python"
        assert exclusions == []

    def test_single_exclusion(self):
        query, exclusions = extract_exclusion_terms("python -senior")
        assert query == "python"
        assert exclusions == ["senior"]

    def test_multiple_exclusions(self):
        query, exclusions = extract_exclusion_terms("react -remote -contract -senior")
        assert query == "react"
        assert set(exclusions) == {"remote", "contract", "senior"}

    def test_complex_query(self):
        query, exclusions = extract_exclusion_terms("python django -senior -staff -principal")
        assert query == "python django"
        assert set(exclusions) == {"senior", "staff", "principal"}
    
    def test_only_exclusions(self):
        query, exclusions = extract_exclusion_terms("-python -junior")
        assert query == ""
        assert set(exclusions) == {"python", "junior"}

class TestTokenization:
    """Test search tokenization."""

    def test_simple_tokenization(self):
        tokens = tokenize_for_search("Software Engineer")
        assert tokens == ["software", "engineer"]

    def test_removes_special_characters(self):
        tokens = tokenize_for_search("Full-stack Developer")
        assert tokens == ["full", "stack", "developer"]

    def test_handles_numbers(self):
        tokens = tokenize_for_search("Python 3.9 Developer")
        assert tokens == ["python", "3.9", "developer"]

    def test_empty_string(self):
        tokens = tokenize_for_search("")
        assert tokens == []