from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, ConfigDict, Field


class TwitchReward(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cost: int = Field(gt=0, strict=True)
    points: int = Field(gt=0, strict=True)


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./sdoycc.db"
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173"
    primary_card_provider: str = "local-demo"
    cardcluster_base_url: str | None = None
    enable_demo_auth: bool = False
    frontend_url: str = "http://localhost:5173/"
    twitch_broadcaster_login: str = "SamDavidOfficial"
    twitch_reward_id: str = ""
    twitch_reward_cost: int = Field(default=1000, gt=0)
    twitch_reward_diamonds: int = Field(default=100, gt=0)
    twitch_rewards: dict[str, TwitchReward] = Field(default_factory=dict)
    session_hours: int = Field(default=24, ge=1, le=168)
    streamerbot_api_key: str = ""
    registration_minutes: int = Field(default=30, ge=5, le=120)
    admin_grant_points_limit: int = Field(default=10000, ge=1, le=1000000)
    admin_grant_cards_limit: int = Field(default=30, ge=1, le=1000)
    admin_grant_packs_limit: int = Field(default=10, ge=1, le=100)
    trade_proposal_hours: int = Field(default=48, ge=1, le=168)
    trade_max_listings: int = Field(default=10, ge=1, le=50)
    trade_max_proposals: int = Field(default=10, ge=1, le=50)
    enable_duel_worker_lab: bool = False
    enable_duel_alpha: bool = False
    duel_max_active_matches: int = Field(default=5, ge=1, le=20)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def demo_enabled(self) -> bool:
        return self.app_env == "development" and self.enable_demo_auth

    @property
    def duel_worker_lab_enabled(self) -> bool:
        return self.app_env == "development" and self.enable_duel_worker_lab

    @property
    def duel_worker_enabled(self) -> bool:
        return self.duel_worker_lab_enabled or (self.app_env == "production" and self.enable_duel_alpha)

settings = Settings()
