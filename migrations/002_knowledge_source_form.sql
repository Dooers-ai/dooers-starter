-- Extend knowledge file source for uploads from send.form (POST /uploads, persist on).
ALTER TABLE agent_knowledge_files DROP CONSTRAINT IF EXISTS agent_knowledge_files_source_check;
ALTER TABLE agent_knowledge_files ADD CONSTRAINT agent_knowledge_files_source_check
  CHECK (source IN ('settings', 'chat', 'form'));
