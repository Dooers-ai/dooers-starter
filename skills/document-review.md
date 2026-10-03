---
id: document-review
name: Revisão de documento anexado
description: Use quando o usuário anexar um documento (PDF, planilha, DOCX) e pedir resumo, revisão, extração de dados ou perguntas sobre o conteúdo.
requires_tools: [get_thread_document_context]
---
1. Chame `get_thread_document_context` com `mode="summary"` para ver a estrutura do documento antes de responder.
2. Para perguntas específicas, chame novamente com `mode="search"` e uma `query` com os termos exatos do usuário (nomes, valores, datas).
3. Para planilhas, cite a aba (`Sheet`) e a linha de onde tirou cada número; não some colunas de cabeça — use `calculate`.
4. Responda com base apenas nos trechos retornados. Se algo não estiver no documento, diga que não consta.
5. Termine oferecendo um próximo passo concreto (ex.: extrair uma tabela, comparar com outro anexo).
