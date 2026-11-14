"""Super Central: serviço público MCP, sem acesso ao computador ou dados privados."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from html import escape

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import HTMLResponse, PlainTextResponse, JSONResponse

PORT = int(os.environ.get("PORT", "18766"))
HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
allowed_hosts = ["localhost:*", "127.0.0.1:*"]
if HOSTNAME:
    allowed_hosts.append(HOSTNAME)

mcp = FastMCP(
    "Super Central",
    instructions=(
        "Use este servidor para pesquisar ferramentas públicas e consultar a compatibilidade. "
        "A versão publicada NÃO acessa arquivos pessoais, não instala programas e não controla o PC."
    ),
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
    json_response=True,
    max_request_body_size=65_536,
    max_sessions=25,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=[],
    ),
)

READONLY_LOCAL = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                 openWorldHint=False, idempotentHint=True)
READONLY_WEB = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                               openWorldHint=True, idempotentHint=True)

CATEGORIES = {
    "desenvolvimento": ["Python", "PHP", "TypeScript", "JavaScript", "testes", "Git"],
    "infraestrutura": ["MCP", "APIs", "Docker", "automação"],
    "multimídia": ["FFmpeg", "Remotion", "processamento de áudio"],
    "segurança": ["avaliação de dependências", "inventário", "políticas de execução"],
}
SOURCES = {"pypi.org", "registry.npmjs.org", "api.github.com"}
USER_AGENT = "SuperCentralPublic/0.2"


def _public_fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=7) as response:
        if urllib.parse.urlsplit(response.url).hostname not in SOURCES:
            raise ValueError("Redirecionamento de domínio bloqueado.")
        payload = response.read(400_001)
        if len(payload) > 400_000:
            raise ValueError("Resposta excede limite.")
        return json.loads(payload)


def _name(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,69}", value):
        raise ValueError("Use um nome de pacote de até 70 caracteres, sem URL ou comandos.")
    return value


@mcp.tool(
    name="central_capabilities",
    description="Use quando quiser conhecer as capacidades públicas e os limites do Super Central.",
    annotations=READONLY_LOCAL,
)
def central_capabilities() -> dict:
    return {
        "version": "public-preview-0.2",
        "mode": "public_catalog_only",
        "categories": CATEGORIES,
        "public_tools": ["central_capabilities", "central_package_details",
                         "central_github_repositories", "central_official_skill"],
        "private_files_access": False,
        "computer_control": False,
        "package_installation": False,
        "message": "A execução local permanece em MCP separado, não disponível neste app público.",
    }


@mcp.tool(
    name="central_package_details",
    description="Use para verificar a versão, licença e descrição pública de um pacote PyPI ou npm pelo nome exato.",
    annotations=READONLY_WEB,
)
def central_package_details(package: str, registry: str = "pypi") -> dict:
    try:
        name = _name(package)
    except ValueError as exc:
        return {"found": False, "error": str(exc)}
    if registry not in {"pypi", "npm"}:
        return {"found": False, "error": "Registro permitido: pypi ou npm."}
    try:
        if registry == "pypi":
            url = "https://pypi.org/pypi/" + urllib.parse.quote(name, safe="") + "/json"
            info = _public_fetch(url).get("info", {})
            return {
                "found": True, "registry": "pypi",
                "name": str(info.get("name", ""))[:100],
                "version": str(info.get("version", ""))[:50],
                "summary": str(info.get("summary", ""))[:500],
                "license": str(info.get("license_expression") or info.get("license") or "não informada")[:100],
                "requires_python": str(info.get("requires_python") or "")[:100],
                "url": "https://pypi.org/project/" + urllib.parse.quote(name, safe="") + "/",
                "installation_performed": False,
            }
        # /latest evita baixar o JSON completo com milhares de versões.
        url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="") + "/latest"
        obj = _public_fetch(url)
        return {
            "found": True, "registry": "npm",
            "name": str(obj.get("name", ""))[:100],
            "version": str(obj.get("version") or "")[:50],
            "summary": str(obj.get("description") or "")[:500],
            "license": str(obj.get("license") or "não informada")[:100],
            "url": "https://www.npmjs.com/package/" + urllib.parse.quote(name, safe=""),
            "installation_performed": False,
        }
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        return {"found": False, "registry": registry, "name": name,
                "reason": type(exc).__name__, "installation_performed": False}



# Fontes oficiais de skills. Nenhuma skill baixada é executada ou instalada.
SKILL_SOURCES = {
    "openai": ("openai", "skills", "skills/.curated"),
    "anthropic": ("anthropics", "skills", "skills"),
}


@mcp.tool(
    name="central_github_repositories",
    description="Pesquise repositórios públicos do GitHub por palavras-chave; retorne nome, link, licença, linguagem, estrelas e descrição. Não clona nem executa códigos.",
    annotations=READONLY_WEB,
)
def central_github_repositories(query: str, limit: int = 5) -> dict:
    if not isinstance(query, str) or len(query.strip()) < 3 or len(query) > 100:
        return {"status": "invalid_query", "results": []}
    if any(ord(ch) < 32 for ch in query):
        return {"status": "invalid_query", "results": []}
    limit = max(1, min(int(limit), 10))
    url = ("https://api.github.com/search/repositories?q=" +
           urllib.parse.quote(query.strip(), safe="") + "&per_page=" + str(limit))
    try:
        data = _public_fetch(url)
        results = []
        for item in data.get("items", [])[:limit]:
            results.append({
                "name": str(item.get("full_name", ""))[:150],
                "url": str(item.get("html_url", ""))[:300],
                "description": str(item.get("description") or "")[:350],
                "stars": int(item.get("stargazers_count") or 0),
                "language": str(item.get("language") or "")[:50],
                "license": str((item.get("license") or {}).get("spdx_id") or "não informada")[:50],
                "archived": bool(item.get("archived", False)),
            })
        return {
            "status": "ok", "results": results, "total_matches": int(data.get("total_count", 0)),
            "disclaimer": "Resultados públicos do GitHub; licenças e segurança não foram auditadas.",
            "installation_performed": False,
        }
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__,
                "results": [], "installation_performed": False}


@mcp.tool(
    name="central_official_skill",
    description="Verifique se uma Agent Skill existe nas coleções públicas oficiais OpenAI/Anthropic e retorne sua descrição e URL. Não executa ou instala a skill.",
    annotations=READONLY_WEB,
)
def central_official_skill(name: str, source: str = "openai") -> dict:
    if source not in SKILL_SOURCES:
        return {"status": "invalid_source", "sources": list(SKILL_SOURCES)}
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,70}", name):
        return {"status": "invalid_name"}
    owner, repo, directory = SKILL_SOURCES[source]
    path = directory + "/" + name + "/SKILL.md"
    url = "https://raw.githubusercontent.com/" + owner + "/" + repo + "/main/" + path
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, "Accept": "text/plain"
        })
        with urllib.request.urlopen(req, timeout=7) as response:
            if urllib.parse.urlsplit(response.url).hostname != "raw.githubusercontent.com":
                raise ValueError("Redirecionamento não autorizado.")
            raw = response.read(100_001)
            if len(raw) > 100_000:
                raise ValueError("Arquivo de skill muito grande.")
        txt = raw.decode("utf-8-sig")
        if not txt.startswith("---"):
            return {"status": "invalid_format", "name": name, "source": source}
        parts = txt.split("---", 2)
        front = parts[1] if len(parts) >= 3 else ""
        description = ""
        for line in front.splitlines():
            if line.lstrip().startswith("description:"):
                description = line.split(":", 1)[1].strip(" '\"")[:400]
                break
        return {
            "status": "found", "name": name, "source": source,
            "description": description,
            "url": "https://github.com/" + owner + "/" + repo + "/tree/main/" +
                   directory + "/" + name,
            "installation_performed": False,
            "warning": "Metadados públicos; conteúdo não executado e segurança não auditada.",
        }
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_found", "name": name, "source": source}
        return {"status": "unavailable", "name": name, "reason": "HTTP_" + str(exc.code)}
    except (OSError, ValueError, UnicodeError) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__, "name": name}


SITE_STYLE = """<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:6vh auto;padding:1rem;line-height:1.7;background:#0b1017;color:#e4eaf0}a{color:#50cf9b}article{border:1px solid #344452;border-radius:16px;padding:1.5rem}nav{display:flex;gap:1rem;flex-wrap:wrap}</style>"""
def _page(title: str, content: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>" + escape(title) + "</title>" + SITE_STYLE +
        "<main><h1>" + escape(title) + "</h1><article>" + content +
        "</article><nav><a href='/'>Início</a><a href='/privacy'>Privacidade</a>"
        "<a href='/terms'>Termos</a><a href='/support'>Suporte</a></nav></main></html>"
    )

async def home(request):
    return _page("Super Central", "<p>Catálogo técnico público de bibliotecas e integrações.</p>"
                 "<p>Oferece ferramentas MCP de consulta a pacotes PyPI/npm, repositórios públicos GitHub e skills oficiais."
                 " Esta versão não controla computadores, não acessa arquivos pessoais e não instala software.</p>"
                 "<p>Endpoint MCP: <code>/mcp</code></p>")

async def privacy(request):
    return _page("Política de Privacidade — Super Central",
                 "<p>Atualização: 14/11/2026.</p>"
                 "<p>O app recebe termos de pesquisa e nomes de pacotes ou skills e os envia a PyPI, npm ou GitHub "
                 "para recuperar metadados públicos. Não exige contas e não recebe "
                 "arquivos locais, credenciais, documentos privados ou histórico pessoal.</p>"
                 "<p>O provedor de hospedagem pode processar endereço IP, horários e logs "
                 "de conexão para segurança e operação, conforme suas políticas.</p>"
                 "<p>Não vendemos dados. Nenhuma consulta é guardada em banco de dados do app."
                 " O uso está sujeito às políticas públicas de PyPI, npm e hospedagem.</p>"
                 "<p>Exclusão: como o app não associa consultas a uma conta, não mantém "
                 "dados de usuário recuperáveis para exclusão. Solicitações sobre logs de "
                 "infraestrutura devem ser tratadas pelo operador de hospedagem.</p>")

async def terms(request):
    return _page("Termos de Uso — Super Central",
                 "<p>Atualização: 14/11/2026.</p>"
                 "<p>O app fornece informações técnicas públicas para fins informativos."
                 " Versões e licenças podem mudar; confirme sempre na fonte original.</p>"
                 "<p>Não são oferecidas operações de instalação, acesso remoto, execução "
                 "de comandos ou alterações em contas por este serviço público.</p>"
                 "<p>É proibido usar o serviço para tráfego abusivo ou interferência em terceiros.</p>")

async def support(request):
    return _page("Suporte — Super Central",
                 "<p>Para dúvidas, solicitações de suporte ou problemas técnicos, abra uma questão "
                 "no <a href='https://github.com/BAZZUKA-ROOT/super-central-public/issues'>"
                 "repositório oficial do Super Central no GitHub</a>.</p>"
                 "<p>Não compartilhe senhas, chaves de API ou dados pessoais em questões públicas.</p>")

async def challenge(request):
    token = os.environ.get("OPENAI_APP_VERIFICATION_TOKEN", "").strip()
    if not token:
        return PlainTextResponse("Challenge not configured", status_code=404)
    return PlainTextResponse(token, headers={"Cache-Control": "no-store"})

async def health(request):
    return JSONResponse({"status": "ok", "mode": "public-catalog-only"})

app = mcp.streamable_http_app()
app.add_route("/", home, methods=["GET"])
app.add_route("/privacy", privacy, methods=["GET"])
app.add_route("/terms", terms, methods=["GET"])
app.add_route("/support", support, methods=["GET"])
app.add_route("/health", health, methods=["GET"])
app.add_route("/.well-known/openai-apps-challenge", challenge, methods=["GET"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning", access_log=False)
