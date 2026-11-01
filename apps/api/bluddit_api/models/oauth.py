"""Private OAuth persistence projections. Never return provider credentials."""

from datetime import datetime

from pydantic import BaseModel, Field


class OAuthAttempt(BaseModel):
    oauth_attempt_id: int
    account_id: int | None
    credential_version: bytes | None = Field(repr=False)
    return_to: str


class ProviderIdentity(BaseModel):
    battle_net_account_id: int
    battletag: str
    access_token: bytes = Field(repr=False)
    obtained_at: datetime
    token_expires_at: datetime


class OAuthRegistration(ProviderIdentity):
    oauth_registration_id: int


class SessionExpiry(BaseModel):
    id: int
    account_id: int
    expires_at: datetime
