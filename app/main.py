import os
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Path, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from .recommender import RecommendationEngine


CSV_PATH = os.getenv("BOOKS_CSV", "book1-100k.csv")
STATE_PATH = os.getenv("DATA_PATH", "data/state.json")


class UserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "ana",
                    "name": "Ana",
                    "preferences": {},
                },
                {
                    "id": "bruno",
                    "name": "Bruno",
                    "preferences": {"1": 5.0, "2": 4.0},
                },
                {
                    "id": "carla",
                    "name": "Carla",
                    "preferences": {"12": 3.0, "14": 5.0},
                },
            ]
        }
    )

    id: str = Field(min_length=1, max_length=100, description="Identificador único do usuário")
    name: str = Field(min_length=1, max_length=200, description="Nome do usuário")
    preferences: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapa opcional: ID do livro -> nota de 0 a 5",
    )


class ItemCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "livro-101",
                    "name": "O Guia do Mochileiro das Galáxias",
                    "authors": "Douglas Adams",
                    "publisher": "Arqueiro",
                    "language": "pt-BR",
                    "year": 2004,
                    "pages": 208,
                    "rating": 4.5,
                    "isbn": "9788576866113",
                },
                {
                    "id": "livro-102",
                    "name": "A Hora da Estrela",
                    "authors": "Clarice Lispector",
                    "publisher": "Rocco",
                    "language": "pt-BR",
                    "year": 1977,
                    "pages": 96,
                    "rating": 4.2,
                    "isbn": "9788532525354",
                },
                {
                    "id": "livro-103",
                    "name": "Livro Sem Editora",
                    "authors": "Autor de Demonstração",
                    "rating": 3.8,
                },
            ]
        }
    )

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    authors: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    year: Optional[int] = None
    pages: Optional[int] = Field(default=None, ge=0)
    rating: float = Field(default=0.0, ge=0, le=5)
    isbn: Optional[str] = None


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"preferences": {"1": 5.0}},
                {"preferences": {"2": 4.0, "14": 5.0}},
                {"preferences": {"3": 2.5, "12": 3.0, "21": 4.5}},
            ]
        }
    )

    preferences: Dict[str, float] = Field(
        description="IDs dos livros obtidos em GET /items e notas de 0 a 5",
    )


engine: RecommendationEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = RecommendationEngine(CSV_PATH, STATE_PATH)
    yield


app = FastAPI(
    title="Sistema de Recomendação de Livros",
    description="API híbrida com filtragem baseada em conteúdo e filtragem colaborativa.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok", "items_loaded": len(engine.items)}


@app.post("/users", status_code=status.HTTP_201_CREATED, tags=["Usuários"])
def create_user(payload: UserCreate):
    try:
        return engine.add_user(payload.id, payload.name, payload.preferences)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/users", tags=["Usuários"])
def list_users():
    return engine.list_users()


@app.get("/users/{user_id}", tags=["Usuários"])
def get_user(
    user_id: str = Path(..., description="ID do usuário", examples=["ana", "bruno"]),
):
    try:
        return engine.get_user(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")


@app.put("/users/{user_id}/preferences", tags=["Usuários"])
def update_preferences(
    payload: PreferenceUpdate,
    user_id: str = Path(..., description="ID do usuário", examples=["ana", "bruno"]),
):
    try:
        return engine.update_preferences(user_id, payload.preferences)
    except KeyError:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/items", status_code=status.HTTP_201_CREATED, tags=["Itens"])
def create_item(payload: ItemCreate):
    try:
        return engine.add_item(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/items", tags=["Itens"])
def list_items(
    limit: int = Query(default=100, ge=1, le=1000, description="Quantidade máxima", examples=[10, 100]),
    offset: int = Query(default=0, ge=0, description="Quantidade a ignorar", examples=[0, 100]),
):
    return engine.list_items(limit=limit, offset=offset)


@app.get("/recommendations/{user_id}", tags=["Recomendações"])
def recommendations(
    user_id: str = Path(..., description="ID do usuário", examples=["ana", "bruno"]),
    limit: int = Query(default=10, ge=1, le=100, description="Quantidade de recomendações", examples=[3, 10, 25]),
):
    try:
        return engine.recommend(user_id, limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
