"""Semantic normalizations shared by merge and provenance tooling."""
import re


def normalize_enable_switches(value):
    """Treat Loon's enable=name and enable=\${name} spellings as the same switch."""
    return re.sub(r"\benable\s*=\s*\$\{([^}]+)\}", r"enable=\1", value)
