from fastapi import FastAPI
from .views import github

app = FastAPI()
app.include_router(github.router)
