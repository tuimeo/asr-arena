import re
import jiwer


def normalize_text(text: str) -> str:
    """Normalize text for CER comparison: remove punctuation, whitespace, lowercase."""
    text = text.lower()
    text = re.sub(r'\s+', '', text)
    # Remove Chinese and English punctuation
    text = re.sub(
        r'[，。！？、；：""''【】《》（）「」『』〈〉·…—'
        r'\.\,\!\?\;\:\"\'\[\]\(\)\-\_\@\#\$\%\^\&\*\+\=\/\\~`]',
        '',
        text,
    )
    return text


def calculate_cer(reference: str, hypothesis: str) -> float | None:
    """
    Calculate Character Error Rate.

    Returns CER as a float (0.0 = perfect), or None if reference is empty.
    """
    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)

    if not ref:
        return None

    return jiwer.cer(ref, hyp)
