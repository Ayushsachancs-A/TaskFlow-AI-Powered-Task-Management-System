
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI,Request, status
from .models import Base
from .database import engine
from .routers import auth, todos, admin, users, ai_assistant
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app = FastAPI(
    title="TodoApp & AI Copilot",
    description="Full-stack FastAPI Todo Application with User-Isolated RAG Assistant",
    version="2.0.0"
)

Base.metadata.create_all(bind=engine)

app.mount('/static', StaticFiles(directory="TodoApp/static"), name='static')


@app.get("/")
def test(request: Request):
    return RedirectResponse(url="/todos/todo-page", status_code=status.HTTP_302_FOUND)

@app.get('/healthy')
def health_check():
    return {'status': 'Healthy'}

app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(ai_assistant.router)

