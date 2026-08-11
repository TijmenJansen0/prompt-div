"""promptdiv - census-grounded prompt augmentation for text-to-image models."""
from .core import DiversityModule, apply_prompt_diversity, enable_diversity

__all__ = ["DiversityModule", "apply_prompt_diversity", "enable_diversity"]
__version__ = "0.1.0"
