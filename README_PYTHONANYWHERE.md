# 🚀 Guia de Deploy no PythonAnywhere

## 📋 Pré-requisitos
- Conta gratuita no [PythonAnywhere](https://www.pythonanywhere.com/)
- Conhecimento básico de Python e Flask

## 🔧 Passo a Passo

### 1. Criar Conta no PythonAnywhere
1. Acesse [www.pythonanywhere.com](https://www.pythonanywhere.com/)
2. Clique em "Create a Beginner account" (gratuito)
3. Complete o cadastro

### 2. Acessar o Console Bash
1. Faça login na sua conta
2. Vá para a aba "Consoles"
3. Clique em "Bash" para abrir um terminal

### 3. Clonar o Repositório
```bash
# Navegar para o diretório home
cd ~

# Clonar seu repositório (substitua pela URL do seu repo)
git clone https://github.com/seu-usuario/OPDV-Omie-Sincronizador.git

# Entrar no diretório do projeto
cd OPDV-Omie-Sincronizador
```

### 4. Configurar Ambiente Virtual
```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 5. Configurar Web App
1. Vá para a aba "Web"
2. Clique em "Add a new web app"
3. Escolha "Flask"
4. Selecione Python 3.11
5. Escolha um nome para sua aplicação (ex: "opdv-omie-sync")

### 6. Configurar WSGI
1. Na aba "Web", clique no link "WSGI configuration file"
2. Substitua todo o conteúdo por:

```python
import sys
import os

# Add the project directory to Python path
path = '/home/seu-usuario/OPDV-Omie-Sincronizador'
if path not in sys.path:
    sys.path.append(path)

# Import the Flask app
from app import app

# For PythonAnywhere
application = app
```

**⚠️ IMPORTANTE:** Substitua `seu-usuario` pelo seu nome de usuário do PythonAnywhere!

### 7. Configurar Variáveis de Ambiente
1. Na aba "Web", vá para "Environment variables"
2. Adicione as seguintes variáveis:
   - `PYTHONANYWHERE_SITE`: `True`
   - `SESSION_SECRET`: `sua-chave-secreta-muito-segura`

### 8. Configurar Diretório de Trabalho
1. Na aba "Web", vá para "Code" section
2. Configure:
   - **Source code**: `/home/seu-usuario/OPDV-Omie-Sincronizador`
   - **Working directory**: `/home/seu-usuario/OPDV-Omie-Sincronizador`

### 9. Reiniciar Aplicação
1. Clique em "Reload" na aba "Web"
2. Aguarde alguns segundos

### 10. Testar Aplicação
1. Acesse sua URL: `https://seu-usuario.pythonanywhere.com`
2. Faça login com:
   - **Usuário**: Vinicius
   - **Senha**: vi131211

## 🔒 Configurações de Segurança

### Alterar Senha Padrão
1. Acesse sua aplicação
2. Faça login com as credenciais padrão
3. **IMPORTANTE**: Altere a senha imediatamente!

### Configurar Credenciais das APIs
1. Vá para a página de configuração
2. Configure as credenciais do OPDV e Omie
3. Teste as conexões

## 📁 Estrutura de Arquivos no PythonAnywhere

```
/home/seu-usuario/
└── OPDV-Omie-Sincronizador/
    ├── app.py
    ├── wsgi.py
    ├── requirements.txt
    ├── models.py
    ├── services/
    ├── templates/
    ├── static/
    └── instance/
        └── integration.db
```

## 🚨 Limitações da Conta Gratuita

- **CPU**: Limitado a 100 segundos por dia
- **Armazenamento**: 512MB
- **Tráfego**: Limitado
- **Domínio**: `seu-usuario.pythonanywhere.com`

## 🔧 Solução de Problemas

### Erro 500
1. Verifique os logs na aba "Web" > "Log files"
2. Confirme se o caminho no WSGI está correto
3. Verifique se todas as dependências foram instaladas

### Erro de Importação
1. Confirme se o ambiente virtual está ativo
2. Verifique se o `requirements.txt` foi instalado
3. Confirme se o caminho no WSGI está correto

### Banco de Dados não Cria
1. Verifique se o diretório `instance` existe
2. Confirme as permissões de escrita
3. Verifique os logs de erro

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs na aba "Web"
2. Consulte a documentação do PythonAnywhere
3. Use o fórum da comunidade PythonAnywhere

## 🎉 Próximos Passos

Após o deploy bem-sucedido:
1. Configure as credenciais das APIs
2. Teste a sincronização
3. Monitore os logs regularmente
4. Considere fazer backup dos dados

---

**Boa sorte com o deploy! 🚀** 