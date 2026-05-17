"""
seed_knowledge.py
Populates the knowledge base with example corporate entries.
Run once to have data for testing the Knowledge Layer integration.

Usage:
    py -3.12 seed_knowledge.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.database   import init_db
from repositories.knowledge import KnowledgeRepository

repo = KnowledgeRepository()


def seed():
    init_db()
    print("Populando base de conhecimento...")

    entries = [
        # ── PADRÕES ──────────────────────────────────────────────────────────
        {
            "category":    "padrao",
            "title":       "Navegação deve ocorrer na mesma aba",
            "description": "Por padrão corporativo, toda navegação interna ao sistema deve ocorrer na mesma aba do browser. Links externos podem abrir em nova aba com target='_blank' e rel='noopener'.",
            "context":     "Aplicável a todos os módulos de navegação",
            "tags":        ["navegação", "aba", "padrão-ui", "frontend"],
        },
        {
            "category":    "padrao",
            "title":       "Ordenação alfabética de cards na Home",
            "description": "Cards na página Home da Área do Gestor devem sempre ser exibidos em ordem alfabética pelo título do card. Novos cards devem respeitar este critério automaticamente.",
            "context":     "Área do Gestor · Home",
            "tags":        ["card", "home", "ordenação", "alfabética", "gestor"],
        },
        {
            "category":    "padrao",
            "title":       "Acesso a funcionalidade não deve disparar consulta automática",
            "description": "Ao acessar uma tela de consulta, nenhuma busca ou consulta de dados deve ser executada automaticamente. O usuário deve acionar explicitamente a pesquisa.",
            "context":     "Módulos de consulta e pesquisa",
            "tags":        ["consulta", "pesquisa", "UX", "padrão"],
        },

        # ── BUGS HISTÓRICOS ───────────────────────────────────────────────────
        {
            "category":    "bug",
            "title":       "Card duplicado após refresh em tela de listagem",
            "description": "Em versão anterior, cards na Home eram duplicados ao pressionar F5 durante o carregamento. Causado por dupla renderização do componente.",
            "context":     "Área do Gestor · Home · Cards",
            "mitigation":  "Implementar controle de estado de carregamento. Usar flag isLoading para evitar dupla renderização.",
            "severity":    "high",
            "tags":        ["card", "home", "duplicação", "refresh", "bug"],
        },
        {
            "category":    "bug",
            "title":       "ISIN inválido não retorna mensagem de erro adequada",
            "description": "Quando um código ISIN inválido é consultado, o sistema retorna tela em branco ao invés de mensagem de erro amigável. Bug identificado na sprint 8.",
            "context":     "Consulta de ISIN",
            "mitigation":  "Validar formato ISIN (2 letras + 10 alfanuméricos) antes de enviar request. Exibir mensagem: 'Código ISIN inválido. Verifique o formato.'",
            "severity":    "critical",
            "tags":        ["ISIN", "validação", "erro", "consulta", "bug"],
        },
        {
            "category":    "bug",
            "title":       "Permissão de acesso não verificada no carregamento do card",
            "description": "Cards eram exibidos para usuários sem permissão. Ao clicar, ocorria erro 403. A verificação de permissão deve ocorrer antes de renderizar o card.",
            "context":     "Área do Gestor · Controle de Acesso",
            "mitigation":  "Verificar perfil do usuário antes de renderizar o card. Ocultar card se sem permissão.",
            "severity":    "critical",
            "tags":        ["permissão", "acesso", "card", "403", "gestor"],
        },

        # ── INTEGRAÇÕES ───────────────────────────────────────────────────────
        {
            "category":    "integ",
            "title":       "API de Consulta ISIN — Endpoint interno",
            "description": "A consulta de códigos ISIN é feita via API interna REST. Endpoint: /api/v1/isin/{codigo}. SLA: resposta em até 3s. Retorna: dados do ativo, emissor, mercado, vencimento.",
            "context":     "Módulo Consulta de ISIN",
            "mitigation":  "Implementar timeout de 5s e mensagem de fallback em caso de indisponibilidade.",
            "tags":        ["ISIN", "API", "REST", "integração", "consulta"],
        },
        {
            "category":    "integ",
            "title":       "Autenticação SSO — Azure AD",
            "description": "O sistema utiliza Azure Active Directory (SSO) para autenticação. Perfis e permissões são sincronizados a cada login. Grupos AD mapeiam para perfis do sistema (Gestor, Analista, Admin).",
            "context":     "Módulo de Autenticação",
            "tags":        ["SSO", "Azure AD", "autenticação", "perfil", "permissão"],
        },

        # ── GLOSSÁRIO ─────────────────────────────────────────────────────────
        {
            "category":    "gloss",
            "title":       "ISIN (International Securities Identification Number)",
            "description": "Código de 12 caracteres que identifica unicamente um ativo financeiro globalmente. Formato: 2 letras (país) + 9 alfanuméricos + 1 dígito verificador. Ex: BRPETROACNOR6.",
            "tags":        ["ISIN", "ativo", "financeiro", "código", "glossário"],
        },
        {
            "category":    "gloss",
            "title":       "Área do Gestor",
            "description": "Portal exclusivo para usuários com perfil 'Gestor'. Agrupa funcionalidades de gestão de carteira, consultas e relatórios. Acessível via menu lateral após login com perfil adequado.",
            "tags":        ["gestor", "portal", "home", "perfil", "área"],
        },

        # ── COMPLIANCE ────────────────────────────────────────────────────────
        {
            "category":    "comp",
            "title":       "Dados de ativos financeiros — LGPD e regulatório CVM",
            "description": "Consultas de dados de ativos financeiros devem respeitar as diretrizes da CVM e LGPD. Dados sensíveis de investidores não devem ser expostos em logs. Auditoria de acesso obrigatória.",
            "context":     "Todos os módulos de consulta financeira",
            "mitigation":  "Implementar log de auditoria para cada consulta de ISIN. Não logar dados pessoais.",
            "severity":    "critical",
            "tags":        ["LGPD", "CVM", "compliance", "auditoria", "ISIN", "financeiro"],
        },

        # ── RISCOS ────────────────────────────────────────────────────────────
        {
            "category":    "risco",
            "title":       "Risco: Acesso não autorizado a funcionalidades restritas",
            "description": "Funcionalidades da Área do Gestor podem ser acessadas por usuários sem perfil adequado via manipulação de URL ou chamada direta à API.",
            "context":     "Área do Gestor",
            "mitigation":  "Validar perfil tanto no frontend (ocultar elementos) quanto no backend (verificar token). Nunca confiar apenas na UI.",
            "severity":    "critical",
            "tags":        ["acesso", "autorização", "segurança", "gestor", "risco"],
        },
        {
            "category":    "risco",
            "title":       "Risco: Indisponibilidade da API de ISIN",
            "description": "A API de consulta ISIN tem histórico de instabilidade em horários de pico (abertura e fechamento de mercado: 9h-10h e 16h-17h).",
            "context":     "Consulta de ISIN",
            "mitigation":  "Implementar retry com backoff exponencial. Exibir mensagem clara de indisponibilidade temporária. Cache de consultas recentes.",
            "severity":    "high",
            "tags":        ["ISIN", "API", "indisponibilidade", "pico", "risco"],
        },

        # ── HEURÍSTICAS ───────────────────────────────────────────────────────
        {
            "category":    "heur",
            "title":       "Sempre testar o comportamento com usuário sem permissão",
            "description": "Para qualquer funcionalidade com controle de acesso, sempre criar cenário de teste com usuário sem a permissão necessária. Verificar: card oculto? API retorna 403? Mensagem adequada?",
            "tags":        ["heurística", "permissão", "acesso", "segurança", "teste"],
        },
        {
            "category":    "heur",
            "title":       "Testar ordenação após inserção de novo item",
            "description": "Quando um requisito define ordenação (alfabética, por data, por prioridade), sempre testar: inserir novo item no meio da lista, no início e no final. Verificar se a ordem é mantida.",
            "tags":        ["heurística", "ordenação", "listagem", "inserção", "teste"],
        },
    ]

    created = 0
    for e in entries:
        try:
            repo.create(**e)
            print(f"  ✓ [{e['category']}] {e['title'][:60]}")
            created += 1
        except Exception as ex:
            print(f"  ✗ Erro: {ex}")

    print(f"\n✅ {created} registros criados na base de conhecimento.")
    print("Agora analise um requisito sobre ISIN ou Área do Gestor para ver o enriquecimento.")


if __name__ == "__main__":
    seed()
