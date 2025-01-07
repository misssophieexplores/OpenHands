from pydantic import BaseModel


class ReviewThread(BaseModel):
    comment: str
    files: list[str]


class GithubIssue(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str
    thread_comments: list[str] | None = None  # Added field for issue thread comments
    closing_issues: list[str] | None = None
    review_comments: list[str] | None = None
    review_threads: list[ReviewThread] | None = None
    thread_ids: list[str] | None = None
    head_branch: str | None = None
    has_merge_conflicts: bool | None = None
    failed_checks: list[dict[str, str | None]] | None = None
