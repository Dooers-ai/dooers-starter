"""The agent itself: one generalist agent, a stable tool surface and progressive Skills.

Read in this order: ``tool_catalog`` (what the model can do), ``skills`` (how creators teach it
procedures without code), ``policies`` (the stable prompt head), ``context`` (volatile per-turn
state), ``tools`` (implementations), ``agent`` (assembly).
"""
