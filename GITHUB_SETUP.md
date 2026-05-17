# 📋 Guia: Publicar no GitHub

Seu repositório local foi inicializado com sucesso! Agora siga os passos abaixo para publicar no GitHub:

## Passo 1: Criar um repositório no GitHub

1. Acesse [github.com](https://github.com) e faça login
2. Clique no ícone **+** (canto superior direito) → **New repository**
3. Preencha os dados:
   - **Repository name**: `qa-system-backend` (ou o nome desejado)
   - **Description**: `Multi-engine QA analysis pipeline with hybrid parallelism`
   - **Visibility**: Escolha **Public** (ou **Private** se preferir)
   - **Initialize this repository with**:
     - ❌ NÃO adicione .gitignore (já temos um)
     - ❌ NÃO adicione README (já temos um)
     - ❌ NÃO adicione licença (opcionalmente, escolha uma)
4. Clique em **Create repository**

## Passo 2: Conectar repositório local ao GitHub

Após criar o repositório no GitHub, você receberá uma página com instruções. Execute os comandos abaixo no PowerShell:

```powershell
# Navegue até a pasta do projeto
cd "C:\projetos\qa-system-backend"

# Adicione o repositório remoto (substitua USER e REPO pelos seus valores)
git remote add origin https://github.com/SEU_USUARIO/qa-system-backend.git

# Renomeie a branch para main (opcional, mas recomendado)
git branch -M main

# Faça o push inicial com credenciais
git push -u origin main
```

## Passo 3: Autenticação GitHub

Ao fazer o push, o Git solicitará sua autenticação. Você tem 2 opções:

### Opção A: Usar GitHub CLI (recomendado)
```powershell
# Instale GitHub CLI se não tiver
choco install gh -y  # ou download de https://github.com/cli/cli

# Faça login
gh auth login

# Responda às perguntas:
# - What is your preferred protocol for Git operations? → HTTPS
# - Authenticate Git with your GitHub credentials? → Yes
# - How would you like to authenticate GitHub CLI? → Paste token
```

### Opção B: Usar Personal Access Token (PAT)
1. GitHub → **Settings** (canto superior direito)
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**
4. Nome: `qa-system-backend-token`
5. Marque: `repo`, `workflow`
6. Clique **Generate token**
7. **Copie o token** (aparece apenas uma vez!)
8. Ao fazer `git push`, use:
   - Username: seu usuário GitHub
   - Password: cole o token

### Opção C: Usar SSH (avançado)
Se já tem SSH configurado:
```powershell
# Use SSH em vez de HTTPS
git remote remove origin
git remote add origin git@github.com:SEU_USUARIO/qa-system-backend.git
git push -u origin main
```

## Passo 4: Verificar push

Após o push ser concluído com sucesso:
- Acesse seu repositório no GitHub: `https://github.com/SEU_USUARIO/qa-system-backend`
- Você deve ver todos os arquivos do projeto

## Próximos passos (opcional)

### Adicionar GitHub Actions CI/CD
Crie `.github/workflows/python.yml`:
```yaml
name: Python tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: pytest tests/
```

### Adicionar badge de status
No `README.md`:
```markdown
![Python tests](https://github.com/SEU_USUARIO/qa-system-backend/workflows/Python%20tests/badge.svg)
```

## Comandos úteis após publicar

```powershell
# Ver status
git status

# Ver commits
git log --oneline

# Atualizar local com mudanças remotas
git pull

# Enviar novas mudanças
git add .
git commit -m "Sua mensagem"
git push
```

---

**Dúvidas?** Consulte [GitHub Docs](https://docs.github.com)

