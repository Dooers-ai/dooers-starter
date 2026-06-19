"""Status constants for training and recruitment domains."""

# Candidate pipeline statuses
STATUS_RECEBIDO = "recebido"
STATUS_ANALISADO = "analisado"
STATUS_CONTATADO = "contatado"
STATUS_COMPORTAMENTAL_RECEBIDO = "comportamental_recebido"
STATUS_EM_PROCESSO = "em_processo"
STATUS_APROVADO = "aprovado"
STATUS_REPROVADO = "reprovado"

PIPELINE_ORDER = [
    STATUS_RECEBIDO,
    STATUS_ANALISADO,
    STATUS_CONTATADO,
    STATUS_COMPORTAMENTAL_RECEBIDO,
    STATUS_EM_PROCESSO,
    STATUS_APROVADO,
    STATUS_REPROVADO,
]

# Attendance response values
RESPOSTA_SIM = "sim"
RESPOSTA_NAO = "nao"
RESPOSTA_PENDENTE = "pendente"

# Training types
TIPO_ONLINE = "online"
TIPO_PRESENCIAL = "presencial"

# Supabase table names
TABELA_CRONOGRAMA = "cronograma"
TABELA_INSCRICOES = "inscricoes"
TABELA_UNIDADES = "unidades"
TABELA_VAGAS = "vagas"
TABELA_CANDIDATOS = "candidatos"
