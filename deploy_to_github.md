# 🚀 Deploy para GitHub

## 📋 Passos para Enviar para o Repositório

### 1. Inicializar Git (se ainda não foi feito)
```bash
# No diretório do projeto
git init
```

### 2. Adicionar o Repositório Remoto
```bash
git remote add origin https://github.com/Mateusdev993/OPDV-Omie-sincronizador.git
```

### 3. Verificar se o Remote foi Adicionado
```bash
git remote -v
```

### 4. Adicionar Todos os Arquivos
```bash
git add .
```

### 5. Fazer o Primeiro Commit
```bash
git commit -m "Preparado para deploy no PythonAnywhere - Sistema de sincronização OPDV-Omie"
```

### 6. Enviar para o GitHub
```bash
git push -u origin main
```

## 🔧 Comandos Completos (Copie e Cole)

```bash
# Navegar para o diretório do projeto
cd OPDV-Omie-Sincronizador

# Inicializar git (se necessário)
git init

# Adicionar remote
git remote add origin https://github.com/Mateusdev993/OPDV-Omie-sincronizador.git

# Verificar remote
git remote -v

# Adicionar arquivos
git add .

# Commit
git commit -m "Preparado para deploy no PythonAnywhere - Sistema de sincronização OPDV-Omie"

# Push
git push -u origin main
```

## 🚨 Se Der Erro de Autenticação

Se pedir usuário e senha:
1. **Usuário**: seu-usuario-github
2. **Senha**: Use um **Personal Access Token** (não sua senha normal)

### Como Criar Personal Access Token:
1. GitHub.com → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Selecione: `repo`, `workflow`
4. Copie o token e use como senha

## ✅ Após o Push Bem-Sucedido

1. Acesse: https://github.com/Mateusdev993/OPDV-Omie-sincronizador
2. Confirme que todos os arquivos estão lá
3. Continue com o deploy no PythonAnywhere usando o README_PYTHONANYWHERE.md

## 📁 Arquivos que Serão Enviados

- ✅ `app.py` - Aplicação Flask principal
- ✅ `wsgi.py` - Configuração WSGI
- ✅ `requirements.txt` - Dependências
- ✅ `models.py` - Modelos do banco
- ✅ `services/` - Serviços OPDV e Omie
- ✅ `templates/` - Templates HTML
- ✅ `static/` - CSS e JS
- ✅ `README_PYTHONANYWHERE.md` - Guia de deploy
- ✅ `.gitignore` - Proteção de arquivos

---

**Boa sorte! 🚀** 