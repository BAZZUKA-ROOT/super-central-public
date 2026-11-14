# Super Central — Public MCP App

**Publicação v0.2.0:** serviço de metadados públicos para ChatGPT/Codex. Não é o agente local do Windows.

## MCP Streamable HTTP

Endpoint: `https://super-central-public.onrender.com/mcp`

Ferramentas, todas anotadas `readOnlyHint=true`:
- `central_capabilities`: resumo de funcionalidades e limites.
- `central_package_details`: nome, versão, licença e descrição de pacotes PyPI/npm.
- `central_github_repositories`: pesquisa de repositórios públicos, sem clone ou execução.
- `central_official_skill`: consulta de existência e metadados de skills oficiais OpenAI/Anthropic.

Recursos de suporte: `/`, `/health`, `/privacy`, `/terms`, `/support`. O desafio de domínio é servido por `/.well-known/openai-apps-challenge`, configurado com a variável `OPENAI_APP_VERIFICATION_TOKEN` recebida no portal da OpenAI (não inventar valor).

## Segurança

- Não recebe arquivos pessoais, senhas nem chaves de usuários.
- Não controla o Windows, não instala pacotes e não executa códigos baixados.
- Somente consultas HTTP a PyPI, npm, API pública GitHub e raw.githubusercontent.com para skills em repositórios oficiais pré-aprovados.
- Entradas e redirecionamentos validados, respostas limitadas em bytes, timeout curto, uso de bibliotecas padrão.
- `gitleaks` executado antes da publicação; não incluir credenciais na imagem/deploy.
- A versão local `D:\SUPER_INTELIGENCIA\agente\central-mcp` não pertence a este repositório.

## Testes

```bash
pip install -r requirements.txt
python app.py
```

Em outro terminal: `python test_public.py`. Para o serviço de produção: `python test_remote.py`.

## Publicação

ZIP de submissão v0.2.0 gerado por `../build_submission.py`. A OpenAI exige Developer Identity verificada, domínio HTTPS verificado por challenge, Scan Tools, 5 testes positivos, 3 negativos, vídeo real de demonstração e envio pelo portal [Plugins](https://platform.openai.com/plugins).

**Não é um clone do Remote Desktop Commander.** Para acessar o computador remotamente de forma pública, é necessário desenvolver vinculação por usuário/dispositivo, autenticação OAuth 2.1, autorização granular de ações, auditoria e regras de privacidade, além das aprovações aplicáveis. Não adicionar acesso arbitrário ao computador no MCP público sem isso.
