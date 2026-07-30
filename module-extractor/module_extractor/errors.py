"""User-facing extractor failures."""


class ExtractorError(RuntimeError):
    """A deterministic validation or pipeline failure."""


class MapFacetError(ExtractorError):
    """One or more map facets failed shape or controlled-value validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            "map facet validation failed:\n- " + "\n- ".join(errors)
        )
