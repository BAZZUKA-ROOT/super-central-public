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
SOURCES = {"pypi.org", "registry.npmjs.org"}
USER_AGENT = "SuperCentralPublic/0.1"


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
        "version": "public-preview-0.1",
        "mode": "public_catalog_only",
        "categories": CATEGORIES,
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
        url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="")
        obj = _public_fetch(url)
        version = obj.get("dist-tags", {}).get("latest", "")
        entry = obj.get("versions", {}).get(version, {})
        return {
            "found": True, "registry": "npm",
            "name": str(obj.get("name", ""))[:100],
            "version": str(version)[:50],
            "summary": str(entry.get("description") or obj.get("description") or "")[:500],
            "license": str(entry.get("license") or "não informada")[:100],
            "url": "https://www.npmjs.com/package/" + urllib.parse.quote(name, safe=""),
            "installation_performed": False,
        }
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        return {"found": False, "registry": registry, "name": name,
                "reason": type(exc).__name__, "installation_performed": False}


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
                 "<p>Oferece ferramentas MCP de consulta a metadados de pacotes PyPI e npm."
                 " Esta versão não controla computadores, não acessa arquivos pessoais e não instala software.</p>"
                 "<p>Endpoint MCP: <code>/mcp</code></p>")

async def privacy(request):
    return _page("Política de Privacidade — Super Central",
                 "<p>Atualização: 14/11/2026.</p>"
                 "<p>O app recebe os nomes dos pacotes consultados e os envia a PyPI ou npm "
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
                 "<p>Em preparação para publicação. Para problemas técnicos, "
                 "consulte a página do desenvolvedor no portal OpenAI após o cadastro."
                 " Este canal será atualizado com contato oficial antes da submissão.</p>")

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
