from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = ""
    rabbitmq_url: str = ""
    redis_url: str = ""
    jwt_secret: str = "ustbite-jwt-secret-change-in-prod"
    # Internal K8s DNS for payment service — override via JWT_SECRET + PAYMENT_SERVICE_URL env vars
    payment_service_url: str = "http://ustbite-payment-service-prod.ustbite-backend.svc.cluster.local:8004"

    class Config:
        env_file = ".env"

settings = Settings()
