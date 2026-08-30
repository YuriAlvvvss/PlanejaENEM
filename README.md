# PlanejaENEM 📚

**PlanejaENEM** é uma aplicação web completa para organização de estudos direcionada aos candidatos do ENEM. A plataforma ajuda o aluno a registrar matérias, gerenciar tarefas de estudo, acompanhar progresso em tempo real e gerar um cronograma personalizado de estudos com base em disponibilidade semanal, tempo diário e data da prova.

## 🎯 Visão Geral

A aplicação foi desenvolvida com **Flask** seguindo a arquitetura robusta de **Application Factory** com **Blueprints**, separando de forma clara as responsabilidades: autenticação, dashboard, gestão de matérias, tarefas e planejamento. O sistema foi projetado para uso individual por usuário, com armazenamento seguro em **SQLite** por padrão.

### ✨ Funcionalidades Principais

- ✅ **Autenticação**: Cadastro e login seguro de usuários com proteção de rotas
- ✅ **Gestão de Matérias**: CRUD completo de disciplinas com prioridades e dificuldades
- ✅ **Gestão de Tarefas**: CRUD de tarefas com prioridade, data prevista e status de conclusão
- ✅ **Dashboard**: Indicadores de progresso, tarefas pendentes e próximas entregas
- ✅ **Planejamento Inteligente**: Geração automática de cronograma de estudos por dia e faixa horária
- ✅ **Edição Manual**: Possibilidade de ajustar sessões do cronograma manualmente
- ✅ **Regeneração Dinâmica**: Refazer o plano de estudos conforme necessário
- ✅ **Health Check**: Monitoramento de saúde via rota `/health`
- ✅ **Logging**: Sistema de logs em `instance/logs/`
- ✅ **Segurança**: Cabeçalhos de segurança, proteção CSRF e cookies seguros
- ✅ **Animações Premium**: Interface moderna com transições suaves e efeitos glassmorphism (veja [PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md))

## 🛠 Stack Tecnológico

| Componente | Tecnologia |
|-----------|-----------|
| **Backend** | Python 3.12 |
| **Framework Web** | Flask 3.1.1 |
| **ORM & Banco de Dados** | Flask-SQLAlchemy 3.1.1 + SQLite |
| **Autenticação** | Flask-Login 0.6.3 |
| **Formulários** | Flask-WTF 1.2.2 + WTForms 3.2.1 |
| **Validação de Email** | email-validator 2.2.0 |
| **Variáveis de Ambiente** | python-dotenv 1.1.0 |
| **Web Server** | Werkzeug 3.1.3 |
| **Frontend** | Bootstrap 5 + HTML/CSS/JavaScript |
| **Containerização** | Docker / Docker Compose |
| **Testes** | pytest 8.3.3 |

## 📁 Estrutura do Projeto

```
PlanejaENEM/
├── app/                           # Pacote principal da aplicação
│   ├── __init__.py               # Factory da aplicação, configuração e setup
│   ├── extensions.py             # Extensões (db, login_manager, csrf)
│   ├── models.py                 # Modelos de dados (User, Subject, Task, StudyPlan, StudySession)
│   ├── auth/                     # Blueprint de autenticação
│   │   ├── __init__.py
│   │   ├── forms.py              # Formulários: RegisterForm, LoginForm, ProfileForm
│   │   └── routes.py             # Rotas: /register, /login, /logout, /profile
│   ├── main/                     # Blueprint principal
│   │   ├── __init__.py
│   │   └── routes.py             # Rotas: /dashboard, /health
│   ├── planner/                  # Blueprint de planejamento
│   │   ├── __init__.py
│   │   └── routes.py             # Rotas: /planner, /generate-plan, /regenerate-plan
│   ├── subjects/                 # Blueprint de matérias/disciplinas
│   │   ├── __init__.py
│   │   ├── forms.py              # Formulário de matéria
│   │   └── routes.py             # Rotas: CRUD de matérias
│   ├── tasks/                    # Blueprint de tarefas
│   │   ├── __init__.py
│   │   ├── forms.py              # Formulário de tarefa
│   │   └── routes.py             # Rotas: CRUD de tarefas e toggle de status
│   ├── static/                   # Arquivos estáticos
│   │   ├── app.js                # JavaScript da aplicação
│   │   ├── style.css             # Estilos padrão
│   │   └── premium.css           # Estilos premium (animações, glassmorphism)
│   └── templates/                # Templates HTML
│       ├── base.html             # Template base
│       ├── dashboard.html        # Dashboard principal
│       ├── auth/
│       │   ├── login.html
│       │   ├── register.html
│       │   └── profile.html
│       ├── includes/
│       │   └── flashes.html      # Componente de mensagens flash
│       ├── planner/
│       │   └── planner.html
│       ├── subjects/
│       │   ├── list.html
│       │   ├── form.html
│       │   └── confirm_delete.html
│       └── tasks/
│           ├── list.html
│           ├── form.html
│           └── confirm_delete.html
├── instance/                      # Diretório de runtime (não versionado)
│   ├── logs/                     # Arquivos de log em execução
│   └── planejaenem.db            # Banco de dados SQLite padrão
├── tests/                        # Suite de testes
│   ├── test_auth.py              # Testes de autenticação
│   ├── test_planner.py           # Testes de planejamento
│   └── test_phase2_quality.py    # Testes de qualidade
├── Dockerfile                    # Configuração Docker
├── docker-compose.yml            # Orquestração Docker Compose
├── requirements.txt              # Dependências Python
├── run.py                        # Entrypoint da aplicação
├── run.sh                        # Script para Linux/macOS
├── run.bat                       # Script para Windows
├── README.md                     # Este arquivo
├── PREMIUM_UPGRADES.md           # Documentação de recursos premium
├── .gitignore
└── .env                          # Variáveis de ambiente (opcional)

## 📋 Pré-requisitos

- **Python** 3.12 ou superior
- **pip** (gerenciador de pacotes Python)
- **Git** (para clonar o repositório)
- **Docker e Docker Compose** (opcional, para execução em containers)
- Navegador moderno com suporte a Bootstrap 5

## 🚀 Instalação e Execução

### Execução Local

#### 1️⃣ Clonar o Repositório

```bash
git clone <url-do-repositorio>
cd PlanejaENEM
```

#### 2️⃣ Criar Ambiente Virtual

```bash
python -m venv venv
```

**Ativar o ambiente virtual:**

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

#### 3️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

#### 4️⃣ Configurar Variáveis de Ambiente (Opcional)

O projeto usa valores padrão caso `.env` não exista. Para personalizar, crie um arquivo `.env` na raiz do projeto:

```env
FLASK_ENV=development
SECRET_KEY=sua-chave-secreta-super-segura
DATABASE_URL=sqlite:////caminho/para/instance/planejaenem.db
PORT=5000
FLASK_DEBUG=1
```

**Variáveis disponíveis:**
- `FLASK_ENV`: `development` (padrão) ou `production`
- `SECRET_KEY`: Chave para assinatura de sessões (gerado automaticamente em dev)
- `DATABASE_URL`: URL do banco de dados (padrão: SQLite local)
- `PORT`: Porta da aplicação (padrão: 5000)
- `FLASK_DEBUG`: Modo debug (0 ou 1)

#### 5️⃣ Executar a Aplicação

```bash
python run.py
```

A aplicação estará disponível em:

```
http://localhost:5000
```

### Execução com Docker

#### 1️⃣ Construir e Executar com Docker Compose

```bash
docker-compose up --build
```

#### 2️⃣ Acessar a Aplicação

```
http://localhost:5000
```

#### 3️⃣ Parar os Containers

```bash
docker-compose down
```

## 🧪 Testes

### Executar a Suite de Testes

```bash
python -m pytest -q
```

### Executar Testes com Cobertura

```bash
python -m pytest --cov=app --cov-report=html
```

### Executar Testes Específicos

```bash
# Testes de autenticação
python -m pytest tests/test_auth.py -v

# Testes de planejamento
python -m pytest tests/test_planner.py -v

# Testes de qualidade
python -m pytest tests/test_phase2_quality.py -v
```

## 🔗 Rotas Principais

### Autenticação
- `GET  /auth/register` - Página de cadastro
- `POST /auth/register` - Submeter cadastro
- `GET  /auth/login` - Página de login
- `POST /auth/login` - Submeter login
- `GET  /auth/logout` - Fazer logout
- `GET  /auth/profile` - Perfil do usuário
- `POST /auth/profile` - Atualizar perfil

### Dashboard
- `GET /` - Dashboard principal (protegida)

### Matérias
- `GET  /subjects` - Listar matérias
- `GET  /subjects/new` - Formulário de nova matéria
- `POST /subjects` - Criar matéria
- `GET  /subjects/<id>/edit` - Formulário de edição
- `POST /subjects/<id>` - Atualizar matéria
- `GET  /subjects/<id>/delete` - Confirmação de exclusão
- `POST /subjects/<id>/delete` - Deletar matéria

### Tarefas
- `GET  /tasks` - Listar tarefas
- `GET  /tasks/new` - Formulário de nova tarefa
- `POST /tasks` - Criar tarefa
- `GET  /tasks/<id>/edit` - Formulário de edição
- `POST /tasks/<id>` - Atualizar tarefa
- `GET  /tasks/<id>/delete` - Confirmação de exclusão
- `POST /tasks/<id>/delete` - Deletar tarefa
- `POST /tasks/<id>/toggle` - Alternar status de conclusão

### Planejamento
- `GET  /planner` - Visualizar cronograma
- `POST /planner/generate-plan` - Gerar novo plano
- `POST /planner/regenerate-plan` - Regenerar plano existente

### Health Check
- `GET /health` - Status da aplicação (público)

## 📖 Fluxo Principal de Uso

1. **Registrar/Login**
   - Acesse `http://localhost:5000` e crie uma conta
   - Faça login com suas credenciais

2. **Configurar Matérias**
   - Acesse `/subjects` para gerenciar disciplinas
   - Adicione suas matérias de estudo
   - Configure prioridade e dificuldade para cada uma

3. **Gerenciar Tarefas**
   - Acesse `/tasks` para criar tarefas de estudo
   - Defina a matéria, data prevista, prioridade e descrição
   - Marque tarefas como concluídas conforme progride

4. **Configurar Plano de Estudo**
   - Acesse `/planner` para definir seus parâmetros:
     - Dias da semana disponíveis
     - Horários de estudo (ex: 08:00-12:00, 14:00-18:00)
     - Tempo total diário de estudo
     - Data da prova ENEM
   
5. **Gerar Cronograma**
   - Clique em "Gerar Plano" para criar sessões de estudo
   - O sistema distribui automaticamente as tarefas ao longo do período
   - Ajuste manualmente conforme necessário

6. **Acompanhar Progresso**
   - Visualize o **Dashboard** com métricas em tempo real:
     - Taxa de conclusão de tarefas
     - Sequência de dias de estudo
     - Cobertura de matérias
     - Próximas tarefas pendentes

## 📊 Modelos de Dados

### User
```python
- id: Identificador único
- username: Nome de usuário único
- email: Email único
- password_hash: Senha criptografada
- created_at: Data de criação
```

### Subject (Matéria)
```python
- id: Identificador único
- user_id: Referência ao usuário
- name: Nome da disciplina
- priority: Prioridade (1-5)
- difficulty: Dificuldade (1-5)
- created_at: Data de criação
```

### Task (Tarefa)
```python
- id: Identificador único
- user_id: Referência ao usuário
- subject_id: Referência à matéria
- title: Título da tarefa
- description: Descrição
- priority: Prioridade (1-5)
- due_date: Data prevista
- completed: Status de conclusão
- created_at: Data de criação
```

### StudyPlan
```python
- id: Identificador único
- user_id: Referência ao usuário
- exam_date: Data da prova
- available_days: Dias disponíveis (JSON)
- available_hours: Horários disponíveis (JSON)
- daily_study_time: Tempo diário em minutos
- created_at: Data de criação
```

### StudySession
```python
- id: Identificador único
- study_plan_id: Referência ao plano
- task_id: Referência à tarefa
- scheduled_date: Data agendada
- time_slot: Faixa horária
- duration_minutes: Duração em minutos
```

## ⚙️ Configuração & Pontos Importantes

### Banco de Dados
- Por padrão, usa **SQLite** armazenado em `instance/planejaenem.db`
- Totalmente compatível com PostgreSQL (ajuste `DATABASE_URL`)
- Migrations podem ser implementadas com Alembic se necessário

### Logging
- Logs da aplicação são gravados em `instance/logs/planejaenem.log`
- Usa `RotatingFileHandler` para evitar crescimento indefinido
- Configure o nível de log ajustando `app/__init__.py`

### Segurança
- ✅ **CSRF Protection**: Ativado em todos os formulários via Flask-WTF
- ✅ **Session Security**: Cookies HTTP-only e SameSite
- ✅ **Password Security**: Hash bcrypt via Werkzeug
- ✅ **Route Protection**: Todas as rotas autenticadas usam `@login_required`
- ⚠️ **HTTPS**: Configure em produção com variável `FLASK_ENV=production`

### Health Check
- Rota `GET /health` responde `{"status": "ok"}` para monitoramento
- Disponível sem autenticação para verificações de LB/monitoring

## 🐛 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'flask'"
**Solução**: Certifique-se de que o ambiente virtual está ativado
```bash
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# Depois instale as dependências
pip install -r requirements.txt
```

### Erro: "Address already in use" na porta 5000
**Solução**: Use uma porta diferente
```bash
python run.py --port 5001
# Ou configure via .env: PORT=5001
```

### Banco de dados não criado
**Solução**: O banco é criado automaticamente na primeira execução. Se precisar resetar:
```bash
# Delete o banco existente
rm instance/planejaenem.db

# Inicie a aplicação novamente
python run.py
```

### Testes falhando
**Solução**: Certifique-se das dependências e que nenhuma instância está rodando
```bash
python -m pytest -v  # modo verbose para mais detalhes
```

## 🚦 Status do Projeto

- ✅ Autenticação funcional e segura
- ✅ CRUD de matérias e tarefas implementado
- ✅ Dashboard com métricas de progresso
- ✅ Geração inteligente de cronograma
- ✅ Suite de testes automatizados (passando)
- ✅ Interface moderna com Bootstrap 5
- ✅ Animações premium e glassmorphism
- ✅ Documentação completa
- 🔄 Pronto para produção com Docker

## 📚 Documentação Adicional

- **[PREMIUM_UPGRADES.md](PREMIUM_UPGRADES.md)** - Recursos premium, animações e melhorias visuais
- Código bem documentado com docstrings em português
- Modelo de banco de dados normalizado
- Scripts de inicialização inclusos (run.py, run.sh, run.bat)

## 🤝 Contribuindo

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

### Diretrizes
- Mantenha a estrutura de Blueprints (separação por módulos)
- Escreva testes para novas funcionalidades
- Siga as conventions de nomes em português
- Atualize o README se necessário

## 📝 Licença

Este projeto é fornecido como está, livre para uso e modificação.

## 👤 Autor

Desenvolvido como ferramenta de preparação para o ENEM.

---

**Última atualização**: Agosto 2026
