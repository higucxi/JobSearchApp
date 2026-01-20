
import re
from Levenshtein import ratio
from typing import Tuple

def normalize_company(company: str) -> str:
    """
    Normalize common company names for deduplication

    Examples:
    - "Google LLC" -> "google"
    - "Microsoft Corporation" -> "microsoft"
    - "Stripe, Inc." -> "stripe"
    
    :param company: given name of company
    :type company: str
    :return: will return a normalized version of the given company name
    :rtype: str
    """

    # convert to lowercase
    normalized = company.lower().strip()

    # remove common suffixes
    suffixes = [
        r'\s+inc\.?$', r'\s+incorporated$',
        r'\s+llc\.?$', r'\s+ltd\.?$',
        r'\s+corporation$', r'\s+corp\.?$',
        r'\s+company$', r'\s+co\.?$',
        r'\s+limited$'
    ]

    # finds all instances of suffix in normalized and replaces it with ''
    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized, flags = re.IGNORECASE)

    # remove special characters except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized

def normalize_title(title: str) -> str:
    """
    Normalize common job titles for deduplication

    Examples:
    - "Software Engineer" -> "software engineer"
    - "SWE" -> "software engineer"
    - "Sr. Software Developer" -> "senior software developer"
    
    :param title: given job title of job posting
    :type title: str
    :return: normalized version of given job title
    :rtype: str
    """
    normalized = title.lower().strip()

    # common abbreviations and variations
    replacements = {
        r'\bswe\b': 'software engineer',
        r'\bsr\.?\b': 'senior',
        r'\bjr\.?\b': 'junior',
        r'\bmgr\.?\b': 'manager',
        r'\bdev\.?\b': 'developer',
        r'\beng\.?\b': 'engineer',
        r'\bqa\b': 'quality assurance',
        r'\bml\b': 'machine learning',
        r'\bai\b': 'artificial intelligence',
        r'\bfe\b': 'frontend',
        r'\bbe\b': 'backend',
        r'\bfs\b': 'fullstack',
        r'\bui/ux\b': 'ui ux',
    }

    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized)

    # remove special characters except spaces and slashes
    normalized = re.sub(r'[^\w\s/]', '', normalized)

    # collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two text strings using Levenshtein ratio.
    
    :param text1: first string
    :type text1: str
    :param text2: second string
    :type text2: str
    :return: score between 0 and 1 indicating how similar the two texts 
             are
    :rtype: float
    """
    if not text1 or not text2:
        return 0.0
    
    # normalize for comparison
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    return ratio(t1, t2)

def is_duplicate_job(
        company1: str, title1: str, desc1: str,
        company2: str, title2: str, desc2: str
) -> Tuple[bool, float]:
    """
    Determine if two jobs are duplicates based on similarity heuristics.
    
    Heuristic:
    - Company must match (normalized)
    - Title similarity >= 0.8 OR
    - Description similarity >= 0.7 (for shorter descriptions)
    
    :param company1: first company's name
    :type company1: str
    :param title1: first job's title
    :type title1: str
    :param desc1: first job's description
    :type desc1: str
    :param company2: second company's name
    :type company2: str
    :param title2: second job's title
    :type title2: str
    :param desc2: second job's description
    :type desc2: str
    :return: returns a tuple where the first value is a boolean based on
             if the two jobs are decidedly the same or not, and the second
             value is the similarity score used to make that decision.
    :rtype: Tuple[bool, float]
    """
    # company must match
    norm_company1 = normalize_company(company1)
    norm_company2 = normalize_company(company2)

    norm_title1 = normalize_title(title1)
    norm_title2 = normalize_title(title2)
    title_similarity = calculate_text_similarity(norm_title1, norm_title2)

    if norm_company1 != norm_company2:
        return False, 0.0
    
    if title_similarity < 0.75:
        return False, title_similarity
    
    # desc scores based on first 1000 characters
    # idea: job title in practice is almost always the same across different websites
    # and many companies list different jobs under the same title if they are filling
    # more than one position. Thus, description must be the main factor in ruling
    # duplicate jobs
    desc_sample1 = desc1[:1000].lower()
    desc_sample2 = desc2[:1000].lower()
    desc_similarity = calculate_text_similarity(desc_sample1, desc_sample2)

    if desc_similarity >= 0.7:
        return True, desc_similarity
    
    return False, desc_similarity

def extract_exclusion_terms(query: str) -> Tuple[str, list]:
    """
    Given a search query, will extract terms to be excluded from
    search results.

    Example:
    - "python -senior -staff" -> ("python", ["senior", "staff"])
    - "react -remote" -> ("react", ["remote"])
    
    :param query: search query
    :type query: str
    :return: query with extracted terms removed, and a list of those excluded terms
    :rtype: Tuple[str, list]
    """
    exclusion_terms = []

    # find all terms starting with minus
    exclusion_pattern = r'-(\w+)'
    matches = re.finditer(exclusion_pattern, query)

    for match in matches:
        exclusion_terms.append(match.group(1).lower())

    # remove exclusion terms from query
    cleaned_query = re.sub(exclusion_pattern, '', query).strip()
    
    # collapse whitespaces
    cleaned_query = re.sub(r'\s+', ' ', cleaned_query)

    return cleaned_query, exclusion_terms

def tokenize_for_search(text: str) -> list:
    """
    tokenization of text for search.
    Converts text to lowercase tokens, removing special characters.
    
    :param text: given text for a search
    :type text: str
    :return: list of corresponding tokens
    :rtype: list
    """
    text = text.lower()

    # keep only alphanumeric and spaces
    # text = re.sub(r'[^\w\s]', ' ', text)

    # # split and filter empty
    # tokens = [t for t in text.split() if t]
    tokens = re.findall(r'\d+(?:\.\d+)?|\w+', text)
    return tokens