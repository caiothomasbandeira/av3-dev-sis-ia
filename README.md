# Sistema de Recomendação de Livros

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker&logoColor=white)
![Pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Dataset Goodreads](https://img.shields.io/badge/Dataset-Goodreads-553B08)

API em Python/FastAPI para recomendar livros do conjunto de dados `book1-100k.csv` do Goodreads. O projeto também inclui Docker, testes unitários e de integração e documentação Swagger.

## Equipe e contribuições

| Integrante | Responsabilidades |
|---|---|
| **Caio Thomas Bandeiras** | Configuração do Docker Compose e do Dockerfile; documentação do README e regras do `.gitignore`; pesquisa e inclusão do conjunto de dados no repositório. |
| **Luis Vinicius Hernani** | Implementação da aplicação na pasta `app/` e configuração das dependências em `requirements.txt`. |
| **Joao Victor Souza** | Testes na pasta `tests/` e scripts de execução na pasta `scripts/`. |

## Modelo

Foi implementado um modelo **híbrido**:

- **Filtragem baseada em conteúdo:** título, autor, editora e idioma são transformados em vetores TF-IDF calculados no próprio projeto. Livros similares aos livros bem avaliados pelo usuário recebem maior pontuação.
- **Filtragem colaborativa:** o sistema compara os perfis de avaliações dos usuários pela similaridade de cosseno e considera as avaliações de usuários semelhantes.
- **Fallback:** a média global do dataset desempata resultados e recomenda livros quando o usuário ainda não possui preferências.

As notas válidas ficam entre `0` e `5`. Ao recomendar, livros já avaliados pelo usuário são excluídos.

## Estrutura

- `app/main.py`: API FastAPI e seus endpoints.
- `app/recommender.py`: carga dos dados, persistência e algoritmo de recomendação.
- `tests/`: testes unitários e de integração.
- `scripts/`: scripts opcionais para instalar as dependências e iniciar a API localmente.
- `book1-100k.csv`: base de dados utilizada, obtida no [Kaggle — Goodreads Book Datasets (10M)](https://www.kaggle.com/datasets/bahramjannesarr/goodreads-book-datasets-10m).
- `Dockerfile` e `docker-compose.yml`: execução em contêiner.

## Execução local

Requisitos: Python 3.11 ou superior.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Também é possível utilizar um dos scripts inclusos para instalar as dependências e iniciar a aplicação:

```powershell
# Windows
.\scripts\run.ps1
```

```sh
# Linux/macOS ou Git Bash
sh scripts/run.sh
```

Os scripts executam a instalação das dependências e iniciam o Uvicorn em `0.0.0.0:8000`.

A API estará disponível em:

- Aplicação: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Docker

```powershell
docker compose up --build
```

Para reconstruir e executar em segundo plano:

```powershell
docker compose up --build -d
```

Para encerrar:

```powershell
docker compose down
```

Os usuários, itens personalizados e preferências são persistidos no volume Docker `recommendation_data`.

## Endpoints

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/health` | Estado da API e quantidade de itens carregados |
| `POST` | `/users` | Criar usuário e preferências iniciais |
| `GET` | `/users` | Listar usuários |
| `GET` | `/users/{id}` | Consultar usuário |
| `PUT` | `/users/{id}/preferences` | Adicionar ou alterar preferências |
| `POST` | `/items` | Cadastrar item personalizado |
| `GET` | `/items?limit=100&offset=0` | Listar itens do dataset |
| `GET` | `/recommendations/{id}?limit=10` | Obter recomendações |

### Exemplo

Criar um usuário sem preferências (mais simples):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/users -ContentType 'application/json' -Body '{"id":"ana","name":"Ana","preferences":{}}'
```

Também é possível informar preferências desde a criação. Os nomes dentro de `preferences` devem ser IDs existentes obtidos em `GET /items`, por exemplo:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/users -ContentType 'application/json' -Body '{"id":"ana","name":"Ana","preferences":{"1":5,"2":4}}'
```

No Swagger `/docs`, cada endpoint com corpo JSON possui exemplos selecionáveis no campo **Examples** do request body:

- **POST `/users`**: usuário sem preferências, usuário com duas preferências ou usuário com preferências de itens diferentes.
- **PUT `/users/{user_id}/preferences`**: uma preferência, duas preferências ou uma atualização com três avaliações.
- **POST `/items`**: livro completo com metadados, livro brasileiro com ISBN ou item mínimo contendo apenas ID, nome, autor e avaliação.

Os exemplos presentes na documentação já usam IDs válidos. Em **POST `/users`**, use `preferences` como `{}` para criar um usuário sem avaliações iniciais:

```json
{
  "id": "ana",
  "name": "Ana",
  "preferences": {}
}
```

Em **PUT `/users/{user_id}/preferences`**, o corpo exibido inicialmente pelo Swagger é:

```json
{
  "preferences": {
    "1": 5
  }
}
```

O Swagger também oferece opções com várias preferências. Use IDs reais exibidos em `GET /items`; por exemplo:

```json
{
  "preferences": {
    "2": 4,
    "14": 5
  }
}
```

Para cadastrar um item completo:

```json
{
  "id": "livro-101",
  "name": "O Guia do Mochileiro das Galáxias",
  "authors": "Douglas Adams",
  "publisher": "Arqueiro",
  "language": "pt-BR",
  "year": 2004,
  "pages": 208,
  "rating": 4.5,
  "isbn": "9788576866113"
}
```

Os campos com parâmetros de consulta e caminho também oferecem exemplos no Swagger, como `GET /items` com limite `10` ou `100`, `GET /users/{user_id}` com os IDs `ana` ou `bruno`, e `GET /recommendations/{user_id}` com limites `3`, `10` ou `25`.

Obter recomendações:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/recommendations/ana?limit=10'
```

Atualizar preferências:

```powershell
Invoke-RestMethod -Method Put -Uri http://localhost:8000/users/ana/preferences -ContentType 'application/json' -Body '{"preferences":{"14":5}}'
```

## Testes

```powershell
python -m pytest -v
```

Os testes cobrem carga do dataset, criação e atualização de usuários, validação de notas, exclusão de itens já avaliados e fluxo HTTP da API.

## Decisões de projeto

- JSON foi escolhido para persistência simples dos dados adicionados pela API, sem exigir banco externo.
- O CSV original é recarregado na inicialização, mantendo os itens pesquisáveis mesmo após o reinício do contêiner.
- `TfidfVectorizer` permite recomendações úteis também para usuários novos que já informaram algumas preferências.
- Validações do Pydantic e da classe de recomendação impedem avaliações fora da faixa e IDs desconhecidos.
