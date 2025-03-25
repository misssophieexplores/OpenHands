class InterimMemory:
    """ Class to store and manage interim results for final result."""

    _memory: str = ""

    @classmethod
    def store(cls, content: str):
        """Appends new content to the memory."""
        cls._memory += f"\n{content}" if cls._memory else content  # Avoid leading newline

    @classmethod
    def retrieve(cls) -> str:
        """Returns the stored interim memory."""
        return cls._memory
    
    @classmethod
    def reset(cls):
        """Clears the stored memory."""
        cls._memory = ""

    @classmethod
    def __str__(cls) -> str:
        """Returns a formatted string of the saved interim results."""
        return f"The following interim results have been saved:\n{cls._memory}" if cls._memory else "No interim results have been saved."