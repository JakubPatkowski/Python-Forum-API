"""Engagement module: lekkie funkcje społecznościowe (polubienia, statystyki).

Świadomie cienki moduł oparty o zapytania SQL (wzorzec jak admin list users),
bez pełnego Clean-Architecture stacka — to proste liczniki, nie agregaty
domenowe. Gdyby urosło (np. typy reakcji, powiadomienia), można przenieść do
modular-monolith z use-case'ami.
"""
