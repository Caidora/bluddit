"""Public handbook records and validated officer edits storing Markdown source."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HandbookSection(BaseModel):
    slug: str
    revision: int
    title: str
    body: str
    updated_at: datetime
    author_account_id: int
    author_name: str


class HandbookContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=30000)


class HandbookCreate(HandbookContent):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")


class HandbookEdit(HandbookContent):
    expected_revision: int = Field(gt=0)


class HandbookDelete(BaseModel):
    expected_revision: int = Field(gt=0)


class HandbookCurrentRevision(BaseModel):
    current_revision: int


class HandbookSectionsResponse(BaseModel):
    sections: list[HandbookSection]


class HandbookRevisionsResponse(BaseModel):
    revisions: list[HandbookSection]
    limit: int
    offset: int
