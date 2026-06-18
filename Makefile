.PHONY: sync-hooks

# Vendored Claude Code session hooks (see specs/sibling-claude-hooks/ in the
# attune umbrella workspace). The hooks are byte-identical copies of attune-ai
# canonical; the drift-guard test enforces it. Re-sync after an upstream change.
ATTUNE_AI_ROOT ?= ../attune-ai
HOOK_FILES = security_guard.py format_on_save.py compact_warning.py spec_orient.py _state.py _resume_prompt.py _transcript_size.py _sdk_gate.py spec_audit.py

sync-hooks:  ## Re-copy session hooks from attune-ai canonical + refresh checksums.
	@if [ ! -d "$(ATTUNE_AI_ROOT)/plugin/hooks" ]; then \
		echo "Error: $(ATTUNE_AI_ROOT)/plugin/hooks not found. Set ATTUNE_AI_ROOT=<path>"; \
		exit 1; \
	fi
	@mkdir -p .claude/hooks
	@for f in $(HOOK_FILES); do \
		cp "$(ATTUNE_AI_ROOT)/plugin/hooks/$$f" ".claude/hooks/$$f"; \
		echo "  synced: $$f"; \
	done
	@(cd .claude/hooks && shasum -a 256 $(HOOK_FILES) > .canonical-sha256)
	@echo "✓ .claude/hooks/.canonical-sha256 refreshed"
