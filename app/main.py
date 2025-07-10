from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.routes import router

# from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://brave-tree-041b43b1e.2.azurestaticapps.net/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
#     app_client_id="<YOUR_CLIENT_ID>",
#     tenant_id="<YOUR_TENANT_ID>",
#     scopes=["openid", "profile", "email"]
# )

app.include_router(router)