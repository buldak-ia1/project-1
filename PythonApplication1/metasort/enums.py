from enum import Enum


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ExecutionMode(StringEnum):
    ANALYZE_ONLY = "analyze_only"
    COPY = "copy"
    MOVE = "move"


class RunStatus(StringEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ClassificationCriterion(StringEnum):
    CHARACTER = "character"
    STYLE = "style"
    SAFETY = "safety"
    PROMPT_FAMILY = "prompt_family"
    MODEL = "model"
    RESOLUTION = "resolution"
    SIMILARITY = "similarity"
    NONE = "none"


class UnclassifiedHandling(StringEnum):
    PLACE_IN_UNCLASSIFIED = "place_in_unclassified"
    KEEP_IN_CATEGORY_ROOT = "keep_in_category_root"
    SKIP = "skip"


class MetadataMissingHandling(StringEnum):
    VISUAL_ONLY = "visual_only"
    MARK_UNKNOWN = "mark_unknown"
    SKIP = "skip"


class GroupType(StringEnum):
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    SAME_PROMPT_FAMILY = "same_prompt_family"
    SAME_MODEL_SERIES = "same_model_series"
    VISUAL_SIMILAR = "visual_similar"
    UNIQUE = "unique"
