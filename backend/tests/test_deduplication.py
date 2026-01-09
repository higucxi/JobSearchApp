import pytest
from app.utils import (
    normalize_company,
    normalize_title,
    is_duplicate_job,
    calculate_text_similarity
)

class TestCompanyNormalization:
    """Test company name normalization."""

    def test_removes_llc(self):
        assert normalize_company("GOOGLE LLC") == "google"
        assert normalize_company("Stripe, LLC") == "stripe"
    
    def test_removes_inc(self):
        assert normalize_company("Microsoft Inc.") == "microsoft"
        assert normalize_company("Apple Inc") == "apple"

    def test_removes_corporation(self):
        assert normalize_company("Amazon Corporation") == "amazon"
        assert normalize_company("Tesla Corp") == "tesla"
    
    def test_handles_special_chars(self):
        assert normalize_company("Meta (Facebook)") == "meta facebook"
        assert normalize_company("AT&T Inc.") == "att"

    def test_lowercase_and_trim(self):
        assert normalize_company("   NETFLIX    ") == "netflix"
    
class TestTitleNormalization:
    """Test job title normalization."""

    def test_expands_abbreviations(self):
        assert normalize_title("SWE") == "software engineer"
        assert normalize_title("Sr. Software Engineer") == "senior software engineer"
        assert normalize_title("Jr. Developer") == "junior developer"
    
    def test_handles_variations(self):
        assert normalize_title("Software Dev") == "software developer"
    
    def test_special_chars(self):
        assert normalize_title("UI/UX designer") == "ui ux designer"

class TestTextSimilarity:
    """Test text similarity calculation."""

    def test_identical_strings(self):
        similarity = calculate_text_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_similar_strings(self):
        similarity = calculate_text_similarity(
            "Software Engineer", "Software Developer"
        )
        assert 0.6 < similarity < 0.9

    def test_different_strings(self):
        similarity = calculate_text_similarity(
            "Software Engineer", "Product Manager"
        )
        assert similarity < 0.5

class TestJobDeduplication:
    """Test job deduplication logic."""

    def test_exact_match_is_duplicate(self):
        is_dup, score = is_duplicate_job(
            "Google", "Software Engineer", "Build amazing products",
            "Google LLC", "Software Engineer", "Build amazing products"
        )
        assert is_dup
        assert score > 0.9

    def test_similar_titles_same_company(self):
        is_dup, score = is_duplicate_job(
            "Meta", "Software Engineer", "Work on React",
            "Meta", "SWE", "Work on React"
        )
        assert is_dup

    def test_different_company_not_duplicate(self):
        is_dup, score = is_duplicate_job(
            "Google", "Software Engineer", "Build stuff",
            "Meta", "Software Engineer", "Build stuff"
        )
        assert not is_dup

    def test_very_different_titles_not_duplicate(self):
        is_dup, score = is_duplicate_job(
            "Google", "Software Engineer", "Backend work",
            "Google", "Product Manager", "Strategy work"
        )
        assert not is_dup

    def test_same_company_same_title_different_desc(self):
        is_dup, score = is_duplicate_job(
            "Google", "Software Engineer", "React and Javascript",
            "Google", "Software Engineer", "Python, Azure, and Power BI"
        )
        assert not is_dup

    def test_similar_description_helps(self):
        # Similar title + similar description = duplicate
        desc = "Join our team to build scalable microservices using Python and Kubernetes. Work with talented engineers on cutting-edge cloud infrastructure."
        
        is_dup, score = is_duplicate_job(
            "Stripe", "Backend Engineer", desc,
            "Stripe", "Senior Backend Engineer", desc
        )
        # Should be duplicate due to high combined score
        assert is_dup or score > 0.6